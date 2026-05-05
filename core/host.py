import asyncio
import os
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from robots import load_robot, list_robots
from core.compliance import ComplianceEngine, BROKER_PROFILES
from core.types import MarketState, Position, BrokerContext

logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

MT5_AVAILABLE = False
mt5 = None

try:
    import MetaTrader5 as _mt5
    mt5 = _mt5
    MT5_AVAILABLE = True
except ImportError:
    pass


@dataclass
class EAConnection:
    sock: object
    symbol: str
    magic: int
    last_hb: datetime
    connected: bool


class TradingHost:
    def __init__(self, broker: str = "FTMO", mode: str = "paper"):
        self.broker = broker
        self.mode = mode
        self.compliance = ComplianceEngine(broker)
        self.connections: dict[str, EAConnection] = {}
        self.robots = {}
        self.running = False

    async def initialize(self) -> bool:
        logger.info(f"Iniciando host en modo {self.mode} para broker {self.broker}")

        if MT5_AVAILABLE:
            if not mt5.initialize():
                logger.error(f"MT5 initialize failed: {mt5.last_error()}")
                return False
            account_info = mt5.account_info()
            if account_info:
                logger.info(f"Cuenta MT5: {account_info.login}, Balance: {account_info.balance}")
        else:
            logger.warning("MT5 no disponible. Solo modo simulación.")

        await self.load_robots()

        self.running = True
        return True

    async def load_robots(self) -> None:
        from pathlib import Path
        robots_dir = Path("robots")
        if not robots_dir.exists():
            logger.warning(f"Directorio robots no existe: {robots_dir}")
            return
        for robot_data in list_robots(robots_dir):
            try:
                robot = load_robot(Path(robot_data["path"]))
                self.robots[robot.magic] = robot
                logger.info(f"Robot cargado: {robot.name} v{robot.version} (magic={robot.magic})")
            except Exception as e:
                logger.error(f"Error cargando robot {robot_data['name']}: {e}")

    async def handle_tick(self, ea_id: str, tick: dict) -> None:
        ms = self.build_market_state(tick)

        for robot in self.robots.values():
            if ms.symbol in robot.symbols:
                signal = robot.detect_signal(ms)
                if signal:
                    can_send, reason = self.compliance.can_send_signal(
                        self._build_ctx(), signal
                    )
                    if can_send:
                        await self.send_signal_to_ea(ea_id, signal)
                    else:
                        logger.warning(f"Señal bloqueada por compliance: {reason}")

                actions = robot.manage_open_positions(ms.open_positions, ms)
                for action in actions:
                    await self.execute_action(ea_id, action)

    def build_market_state(self, tick: dict) -> MarketState:
        symbol = tick.get("sym", "EURUSD")
        timeframe = "M5"
        bars = tick.get("bars", [])
        positions = tick.get("positions", [])

        if MT5_AVAILABLE and mt5:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
            if rates is not None:
                bars = [
                    {
                        "time": r["time"],
                        "open": r["open"],
                        "high": r["high"],
                        "low": r["low"],
                        "close": r["close"],
                        "volume": r["tick_volume"]
                    }
                    for r in rates
                ]

            mt5_positions = mt5.positions_get()
            if mt5_positions:
                positions = [
                    Position(
                        ticket=p.ticket,
                        magic=p.magic,
                        symbol=p.symbol,
                        side="buy" if p.type == mt5.ORDER_TYPE_BUY else "sell",
                        volume=p.volume,
                        price_open=p.price_open,
                        sl=p.sl,
                        tp=p.tp,
                        profit=p.profit,
                        opened_at=datetime.fromtimestamp(p.time, tz=timezone.utc),
                        comment=p.comment or ""
                    )
                    for p in mt5_positions
                ]

            account = mt5.account_info()
            equity = account.equity if account else 0
            balance = account.balance if account else 0
        else:
            equity = tick.get("equity", 10000)
            balance = tick.get("balance", 10000)

        return MarketState(
            symbol=symbol,
            timeframe=timeframe,
            bid=tick.get("bid", 0),
            ask=tick.get("ask", 0),
            spread_pts=tick.get("spread_pts", 0),
            atr_pts=tick.get("atr_pts", 0),
            bars=bars,
            server_time=datetime.now(timezone.utc),
            account_equity=equity,
            account_balance=balance,
            open_positions=positions
        )

    def _build_ctx(self) -> BrokerContext:
        if MT5_AVAILABLE and mt5:
            account = mt5.account_info()
            positions = mt5.positions_get()
            equity = account.equity if account else 0
            balance = account.balance if account else 0
            drawdown_pct = ((balance - equity) / balance * 100) if balance > 0 else 0
            return BrokerContext(
                open_positions_count=len(positions) if positions else 0,
                equity_drawdown_pct=drawdown_pct,
                daily_drawdown_pct=drawdown_pct,
                strategy_capital_used=0
            )
        return BrokerContext(
            open_positions_count=0,
            equity_drawdown_pct=0,
            daily_drawdown_pct=0,
            strategy_capital_used=0
        )

    async def send_signal_to_ea(self, ea_id: str, signal) -> None:
        if ea_id not in self.connections:
            logger.warning(f"EA {ea_id} no conectado")
            return

        msg = {
            "op": "open",
            "req_id": self._next_req_id(),
            "symbol": signal.symbol,
            "side": signal.side,
            "volume": signal.volume,
            "sl": signal.sl,
            "tp": signal.tp,
            "magic": signal.magic,
            "comment": signal.comment
        }
        logger.info(f"Enviando señal a EA {ea_id}: {msg}")

    async def execute_action(self, ea_id: str, action) -> None:
        logger.info(f"Ejecutando action: {action}")

    def _next_req_id(self) -> int:
        return random.randint(1000000, 9999999)

    async def shutdown(self) -> None:
        self.running = False
        if MT5_AVAILABLE and mt5:
            mt5.shutdown()
        logger.info("Host detenido")


async def main():
    broker = os.getenv("BROKER", "FTMO")
    mode = os.getenv("MODE", "paper")

    host = TradingHost(broker=broker, mode=mode)

    if not await host.initialize():
        logger.error("Fallo inicializando host. Saliendo.")
        return

    logger.info("Host iniciado correctamente. Presiona Ctrl+C para detener.")

    try:
        while host.running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await host.shutdown()


if __name__ == "__main__":
    asyncio.run(main())