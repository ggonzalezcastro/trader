from datetime import datetime, time
from typing import Optional
import pandas as pd
from robots.base import Robot
from core.types import MarketState, Signal, Action, Position

class FxGerardBOSContinuation(Robot):
    name = "fxgerard-bos-continuation"
    version = "0.1.0"

    def __init__(
        self,
        atr_period: int = 14,
        atr_mult_dist: float = 1.5,
        rr: float = 2.0,
        risk_pct: float = 0.5,
        ema_period: int = 50,
        bos_period: int = 20,
        killzones: list[list[str]] = None,
    ):
        self.atr_period = atr_period
        self.atr_mult_dist = atr_mult_dist
        self.rr = rr
        self.risk_pct = risk_pct
        self.ema_period = ema_period
        self.bos_period = bos_period
        self.killzones = killzones or [["08:00", "11:00"], ["13:00", "16:00"]]

    def _in_killzone(self, dt: datetime) -> bool:
        t = dt.time()
        for start_str, end_str in self.killzones:
            start = time.fromisoformat(start_str)
            end = time.fromisoformat(end_str)
            if start <= t <= end:
                return True
        return False

    def _ema(self, df: pd.DataFrame, period: int) -> pd.Series:
        return df["close"].ewm(span=period, adjust=False).mean()

    def _atr(self, df: pd.DataFrame, n: int = 14) -> float:
        high = df["high"]
        low = df["low"]
        close = df["close"]
        prev_close = close.shift(1)
        tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        return tr.rolling(n).mean().iloc[-1]

    def _atr_rising(self, df: pd.DataFrame, n: int = 14) -> bool:
        atr_curr = self._atr(df, n)
        atr_prev = self._atr(df.iloc[:-1], n)
        return atr_curr > atr_prev

    def _detect_bos(self, df: pd.DataFrame, period: int, direction: str) -> bool:
        if len(df) < period * 2:
            return False
        swing_vals = []
        for i in range(period, len(df) - period):
            if direction == "bullish":
                if df["high"].iloc[i] == df["high"].iloc[i - period:i + period + 1].max():
                    swing_vals.append(df["high"].iloc[i])
            else:
                if df["low"].iloc[i] == df["low"].iloc[i - period:i + period + 1].min():
                    swing_vals.append(df["low"].iloc[i])
        if len(swing_vals) < 2:
            return False
        if direction == "bullish":
            return swing_vals[-1] > swing_vals[-2]
        return swing_vals[-1] < swing_vals[-2]

    def _find_order_block(self, df: pd.DataFrame, direction: str, lookback: int = 5) -> Optional[float]:
        for i in range(len(df) - lookback, len(df) - 1):
            if direction == "bullish":
                if df.iloc[i]["close"] < df.iloc[i]["open"]:
                    return df.iloc[i]["low"]
            else:
                if df.iloc[i]["close"] > df.iloc[i]["open"]:
                    return df.iloc[i]["high"]
        return None

    def _htf_trend(self, ema_vals: pd.Series) -> str:
        if len(ema_vals) < 2:
            return "neutral"
        return "bullish" if ema_vals.iloc[-1] > ema_vals.iloc[-10] else "bearish"

    def detect_signal(self, ms: MarketState) -> Optional[Signal]:
        dt = ms.server_time
        if not self._in_killzone(dt):
            return None

        bars = ms.bars
        if len(bars) < max(self.bos_period * 2, self.ema_period) + 5:
            return None

        df = pd.DataFrame(bars)
        atr = self._atr(df, self.atr_period)
        ema = self._ema(df, self.ema_period)

        if not self._atr_rising(df, self.atr_period):
            return None

        htf = self._htf_trend(ema)
        last_bar = bars[-1]
        prev_bar = bars[-2]

        vwap = ms.vwap if ms.vwap else (df["high"].iloc[-1] + df["low"].iloc[-1]) / 2

        side = None
        entry = last_bar["close"]
        ob_level = None

        if last_bar["close"] > ema.iloc[-1] and htf == "bullish":
            if self._detect_bos(df, self.bos_period, "bullish"):
                ob_level = self._find_order_block(df, "bullish")
                if ob_level and last_bar["close"] > ob_level:
                    side = "buy"
        elif last_bar["close"] < ema.iloc[-1] and htf == "bearish":
            if self._detect_bos(df, self.bos_period, "bearish"):
                ob_level = self._find_order_block(df, "bearish")
                if ob_level and last_bar["close"] < ob_level:
                    side = "sell"

        if side is None:
            return None

        atr_dist = self.atr_mult_dist * atr

        if side == "sell":
            sl = entry + atr_dist
            tp = entry - atr_dist * self.rr
        else:
            sl = entry - atr_dist
            tp = entry + atr_dist * self.rr

        sl_pips = abs(entry - sl) / 0.0001
        volume = self._size(ms, sl_pips)

        return Signal(
            side=side,
            symbol=ms.symbol,
            volume=volume,
            sl=sl,
            tp=tp,
            magic=self.magic,
            comment=f"bos-continuation|htf={htf}|ob={ob_level:.5f}" if ob_level else f"bos-continuation|htf={htf}",
            setup="bos-continuation",
            confidence=0.8,
        )

    def _size(self, ms: MarketState, sl_dist: float) -> float:
        equity = ms.account_equity
        risk_amount = equity * (self.risk_pct / 100)
        sl_price = sl_dist * 0.0001
        if sl_price == 0:
            return 0.01
        return round(risk_amount / sl_price, 2)

    def manage_open_positions(self, positions: list[Position], ms: MarketState) -> list[Action]:
        actions = []
        df = pd.DataFrame(ms.bars)
        ema = self._ema(df, self.ema_period)
        vwap = ms.vwap if ms.vwap else (df["high"].iloc[-1] + df["low"].iloc[-1]) / 2

        for pos in positions:
            pnl = pos.profit
            entry = pos.price_open

            if pnl >= 1.0:
                if pos.side == "buy" and vwap > entry:
                    new_sl = vwap
                    if new_sl > pos.sl:
                        actions.append(Action(op="modify", payload={"ticket": pos.ticket, "sl": new_sl}))
                elif pos.side == "sell" and vwap < entry:
                    new_sl = vwap
                    if new_sl < pos.sl:
                        actions.append(Action(op="modify", payload={"ticket": pos.ticket, "sl": new_sl}))

            if pnl >= 1.5 * self.rr:
                actions.append(Action(op="close", payload={"ticket": pos.ticket, "reason": "target"}))
            elif not self._in_killzone(ms.server_time) and pnl < -1.5 * self.rr:
                actions.append(Action(op="close", payload={"ticket": pos.ticket, "reason": "time-stop"}))

        return actions