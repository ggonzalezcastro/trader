from datetime import datetime, time
from typing import Optional
import pandas as pd
from robots.base import Robot
from core.types import MarketState, Signal, Action, Position

class FxGerardVWAPReversal(Robot):
    name = "fxgerard-vwap-reversal"
    version = "0.1.0"

    def __init__(
        self,
        atr_period: int = 14,
        atr_mult_dist: float = 1.5,
        rr: float = 2.0,
        risk_pct: float = 0.5,
        killzones: list[list[str]] = None,
    ):
        self.atr_period = atr_period
        self.atr_mult_dist = atr_mult_dist
        self.rr = rr
        self.risk_pct = risk_pct
        self.killzones = killzones or [["08:00", "11:00"], ["13:00", "16:00"]]

    def _in_killzone(self, dt: datetime) -> bool:
        t = dt.time()
        for start_str, end_str in self.killzones:
            start = time.fromisoformat(start_str)
            end = time.fromisoformat(end_str)
            if start <= t <= end:
                return True
        return False

    def _vwap(self, df: pd.DataFrame) -> float:
        if len(df) < 2:
            return df.iloc[-1]["close"]
        day_start = df[df["time"] >= df.iloc[0]["time"].replace(hour=0, minute=0, second=0)].index[0]
        session_df = df.loc[day_start:]
        typical = (df["high"] + df["low"] + df["close"]) / 3
        volume = df["volume"] if "volume" in df.columns else pd.Series(1, index=df.index)
        cumulative_tpv = (typical * volume).cumsum()
        cumulative_vol = volume.cumsum()
        return cumulative_tpv.iloc[-1] / cumulative_vol.iloc[-1]

    def _atr(self, df: pd.DataFrame, n: int = 14) -> float:
        high = df["high"]
        low = df["low"]
        close = df["close"]
        prev_close = close.shift(1)
        tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        return tr.rolling(n).mean().iloc[-1]

    def _is_pin_bear(self, bar: dict) -> bool:
        body = abs(bar["close"] - bar["open"])
        upper_shadow = bar["high"] - max(bar["open"], bar["close"])
        lower_shadow = min(bar["open"], bar["close"]) - bar["low"]
        total_range = bar["high"] - bar["low"]
        if total_range == 0:
            return False
        return upper_shadow / total_range > 0.6 and body / total_range < 0.3

    def _is_pin_bull(self, bar: dict) -> bool:
        body = abs(bar["close"] - bar["open"])
        upper_shadow = bar["high"] - max(bar["open"], bar["close"])
        lower_shadow = min(bar["open"], bar["close"]) - bar["low"]
        total_range = bar["high"] - bar["low"]
        if total_range == 0:
            return False
        return lower_shadow / total_range > 0.6 and body / total_range < 0.3

    def detect_signal(self, ms: MarketState) -> Optional[Signal]:
        dt = ms.server_time
        if not self._in_killzone(dt):
            return None

        bars = ms.bars
        if len(bars) < self.atr_period + 2:
            return None

        df = pd.DataFrame(bars)
        atr = self._atr(df, self.atr_period)
        vwap = self._vwap(df) if ms.vwap is None else ms.vwap
        last_bar = bars[-1]
        prev_bar = bars[-2]

        dist_to_vwap = abs(last_bar["close"] - vwap)
        atr_distance = self.atr_mult_dist * atr

        if dist_to_vwap < atr_distance:
            return None

        side = None
        if last_bar["close"] > vwap and prev_bar["close"] <= vwap and self._is_pin_bear(prev_bar):
            side = "sell"
        elif last_bar["close"] < vwap and prev_bar["close"] >= vwap and self._is_pin_bull(prev_bar):
            side = "buy"

        if side is None:
            return None

        entry = last_bar["close"]
        if side == "sell":
            sl = entry + atr_distance
            tp = entry - atr_distance * self.rr
        else:
            sl = entry - atr_distance
            tp = entry + atr_distance * self.rr

        spread_pips = ms.spread_pts / 10
        sl_pips = abs(entry - sl) / 0.0001
        volume = self._size(ms, sl_pips)

        return Signal(
            side=side,
            symbol=ms.symbol,
            volume=volume,
            sl=sl,
            tp=tp,
            magic=self.magic,
            comment=f"vwap-reversal|dist={dist_to_vwap:.1f}|atr={atr:.1f}",
            setup="vwap-reversal",
            confidence=0.7,
        )

    def _size(self, ms: MarketState, sl_dist: float) -> float:
        equity = ms.account_equity
        risk_amount = equity * (self.risk_pct / 100)
        sl_price = sl_dist * 0.0001
        if sl_price == 0:
            return 0.01
        return round(risk_amount / sl_price, 2)

    def manage_open_positions(self, positions: list[Position], ms: MarketState) -> list[Action]:
        if not positions:
            return []

        actions = []
        vwap = ms.vwap
        df = pd.DataFrame(ms.bars)
        atr = self._atr(df, self.atr_period)

        for pos in positions:
            pnl = pos.profit
            entry = pos.price_open
            sl = pos.sl

            if pos.side == "buy" and vwap is not None:
                if pos.price_open < vwap < entry:
                    new_sl = vwap
                    if new_sl > sl:
                        actions.append(Action(op="modify", payload={"ticket": pos.ticket, "sl": new_sl}))
                if pnl >= 0.5 * abs(entry - sl) / 0.0001 * 10:
                    new_sl = entry + 0.00005
                    if new_sl > sl:
                        actions.append(Action(op="modify", payload={"ticket": pos.ticket, "sl": new_sl}))
            elif pos.side == "sell" and vwap is not None:
                if pos.price_open > vwap > entry:
                    new_sl = vwap
                    if new_sl < sl:
                        actions.append(Action(op="modify", payload={"ticket": pos.ticket, "sl": new_sl}))
                if pnl >= 0.5 * abs(entry - sl) / 0.0001 * 10:
                    new_sl = entry - 0.00005
                    if new_sl < sl:
                        actions.append(Action(op="modify", payload={"ticket": pos.ticket, "sl": new_sl}))

            if not self._in_killzone(ms.server_time):
                if pnl > 0:
                    actions.append(Action(op="close", payload={"ticket": pos.ticket, "reason": "time-stop"}))
                elif pnl < -2 * atr:
                    actions.append(Action(op="close", payload={"ticket": pos.ticket, "reason": "atr-stop"}))

        return actions