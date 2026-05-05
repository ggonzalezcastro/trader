from datetime import datetime, time
from typing import Optional
import pandas as pd
from robots.base import Robot
from core.types import MarketState, Signal, Action, Position

class FxGerardSweepCHoCH(Robot):
    name = "fxgerard-sweep-choch"
    version = "0.1.0"

    def __init__(
        self,
        atr_period: int = 14,
        atr_mult_dist: float = 1.5,
        rr: float = 2.0,
        risk_pct: float = 0.5,
        swing_period: int = 20,
        killzones: list[list[str]] = None,
    ):
        self.atr_period = atr_period
        self.atr_mult_dist = atr_mult_dist
        self.rr = rr
        self.risk_pct = risk_pct
        self.swing_period = swing_period
        self.killzones = killzones or [["08:00", "11:00"], ["13:00", "16:00"]]

    def _in_killzone(self, dt: datetime) -> bool:
        t = dt.time()
        for start_str, end_str in self.killzones:
            start = time.fromisoformat(start_str)
            end = time.fromisoformat(end_str)
            if start <= t <= end:
                return True
        return False

    def _swing_highs_lows(self, df: pd.DataFrame, period: int):
        highs = []
        lows = []
        for i in range(period, len(df) - period):
            if df["high"].iloc[i] == df["high"].iloc[i - period:i + period + 1].max():
                highs.append((i, df["high"].iloc[i]))
            if df["low"].iloc[i] == df["low"].iloc[i - period:i + period + 1].min():
                lows.append((i, df["low"].iloc[i]))
        return highs, lows

    def _find_last_sweep(self, highs: list, lows: list, bars: list, direction: str) -> Optional[dict]:
        if direction == "bullish":
            if not lows:
                return None
            last_low_idx, last_low = lows[-1]
            for i in range(last_low_idx + 1, len(bars)):
                if bars[i]["high"] > last_low and bars[i]["close"] < bars[i]["open"]:
                    return {"type": "sweep", "idx": i, "level": last_low, "dir": "bullish"}
        else:
            if not highs:
                return None
            last_high_idx, last_high = highs[-1]
            for i in range(last_high_idx + 1, len(bars)):
                if bars[i]["low"] < last_high and bars[i]["close"] > bars[i]["open"]:
                    return {"type": "sweep", "idx": i, "level": last_high, "dir": "bearish"}
        return None

    def _detect_bos_choch(self, df: pd.DataFrame, direction: str) -> bool:
        if len(df) < self.swing_period * 2:
            return False
        highs, lows = self._swing_highs_lows(df, self.swing_period)
        if direction == "bullish" and len(lows) >= 2:
            return lows[-1][1] > lows[-2][1]
        elif direction == "bearish" and len(highs) >= 2:
            return highs[-1][1] < highs[-2][1]
        return False

    def _atr(self, df: pd.DataFrame, n: int = 14) -> float:
        high = df["high"]
        low = df["low"]
        close = df["close"]
        prev_close = close.shift(1)
        tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        return tr.rolling(n).mean().iloc[-1]

    def detect_signal(self, ms: MarketState) -> Optional[Signal]:
        dt = ms.server_time
        if not self._in_killzone(dt):
            return None

        bars = ms.bars
        if len(bars) < self.swing_period * 2 + 5:
            return None

        df = pd.DataFrame(bars)
        atr = self._atr(df, self.atr_period)

        highs, lows = self._swing_highs_lows(df, self.swing_period)
        if not highs or not lows:
            return None

        last_high_idx = highs[-1][0]
        last_low_idx = lows[-1][0]

        last_bar = bars[-1]
        prev_bar = bars[-2]

        sweep = None
        side = None

        if last_high_idx > last_low_idx:
            if self._detect_bos_choch(df.iloc[:last_high_idx + 1], "bullish"):
                if prev_bar["low"] < lows[-1][1] and last_bar["close"] > prev_bar["high"]:
                    sweep = {"level": lows[-1][1], "dir": "bullish"}
                    side = "buy"
        else:
            if self._detect_bos_choch(df.iloc[:last_low_idx + 1], "bearish"):
                if prev_bar["high"] > highs[-1][1] and last_bar["close"] < prev_bar["low"]:
                    sweep = {"level": highs[-1][1], "dir": "bearish"}
                    side = "sell"

        if sweep is None:
            return None

        entry = last_bar["close"]
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
            comment=f"sweep-choch|sweep={sweep['level']:.5f}",
            setup="sweep-choch",
            confidence=0.75,
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
        for pos in positions:
            pnl = pos.profit
            if pnl > 20:
                new_sl = pos.price_open + 0.00010 if pos.side == "buy" else pos.price_open - 0.00010
                if pos.side == "buy" and new_sl > pos.sl:
                    actions.append(Action(op="modify", payload={"ticket": pos.ticket, "sl": new_sl}))
                elif pos.side == "sell" and new_sl < pos.sl:
                    actions.append(Action(op="modify", payload={"ticket": pos.ticket, "sl": new_sl}))
            if not self._in_killzone(ms.server_time) and pnl < -30:
                actions.append(Action(op="close", payload={"ticket": pos.ticket, "reason": "time-stop"}))
        return actions