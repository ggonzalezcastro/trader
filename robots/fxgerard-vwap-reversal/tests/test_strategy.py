import pytest
from datetime import datetime
from core.types import MarketState, Position, Signal
from robots.fxgerard_vwap_reversal.strategy import FxGerardVWAPReversal

def create_market_state(bars, server_time, symbol="EURUSD", timeframe="M5"):
    return MarketState(
        symbol=symbol,
        timeframe=timeframe,
        bid=bars[-1]["close"],
        ask=bars[-1]["close"] + 0.0001,
        spread_pts=10,
        atr_pts=100,
        bars=bars,
        vwap=bars[-1]["close"],
        session="london",
        server_time=server_time,
        account_equity=10000,
        account_balance=10000,
        open_positions=[],
    )

def create_bar(open, high, low, close, time_str):
    return {
        "open": open,
        "high": high,
        "low": low,
        "close": close,
        "volume": 1000,
        "time": datetime.fromisoformat(time_str),
    }

class TestFxGerardVWAPReversal:

    def setup_method(self):
        self.strategy = FxGerardVWAPReversal(
            atr_period=14,
            atr_mult_dist=1.5,
            rr=2.0,
            risk_pct=0.5,
            killzones=[["08:00", "11:00"], ["13:00", "16:00"]],
        )

    def test_in_killzone_london(self):
        dt = datetime(2024, 1, 15, 9, 30)
        assert self.strategy._in_killzone(dt) is True

    def test_in_killzone_ny(self):
        dt = datetime(2024, 1, 15, 14, 30)
        assert self.strategy._in_killzone(dt) is True

    def test_outside_killzone(self):
        dt = datetime(2024, 1, 15, 7, 30)
        assert self.strategy._in_killzone(dt) is False

        dt = datetime(2024, 1, 15, 12, 30)
        assert self.strategy._in_killzone(dt) is False

    def test_detect_signal_outside_killzone_returns_none(self):
        bars = [
            create_bar(1.0850, 1.0860, 1.0845, 1.0855, "2024-01-15 07:30:00"),
            create_bar(1.0855, 1.0865, 1.0850, 1.0860, "2024-01-15 07:35:00"),
        ]
        bars.extend([create_bar(1.0860, 1.0868, 1.0858, 1.0862, f"2024-01-15 07:{40+i}:00") for i in range(12)])

        ms = create_market_state(bars, datetime(2024, 1, 15, 7, 45))
        result = self.strategy.detect_signal(ms)
        assert result is None

    def test_detect_signal_bearish_pin_bar_crossing_vwap(self):
        bars = []
        base_time = datetime(2024, 1, 15, 8, 0)
        for i in range(14):
            t = base_time.replace(minute=i * 5)
            bars.append(create_bar(1.0850, 1.0860, 1.0845, 1.0855, t.isoformat()))

        vwap_price = 1.0855
        bars[-2] = create_bar(1.0855, 1.0870, 1.0854, 1.0855, base_time.replace(minute=60).isoformat())
        bars[-2]["high"] = 1.0875
        bars[-1] = create_bar(1.0855, 1.0860, 1.0852, 1.0856, base_time.replace(minute=65).isoformat())
        bars[-1]["close"] = 1.0860

        ms = create_market_state(bars, datetime(2024, 1, 15, 9, 0), server_time=datetime(2024, 1, 15, 9, 5))
        ms.vwap = vwap_price

        result = self.strategy.detect_signal(ms)
        assert result is not None
        assert result.side == "sell"
        assert result.setup == "vwap-reversal"

    def test_detect_signal_bullish_pin_bar_crossing_vwap(self):
        bars = []
        base_time = datetime(2024, 1, 15, 13, 0)
        for i in range(14):
            t = base_time.replace(minute=i * 5)
            bars.append(create_bar(1.0855, 1.0860, 1.0850, 1.0852, t.isoformat()))

        bars[-2] = create_bar(1.0850, 1.0855, 1.0830, 1.0835, base_time.replace(minute=60).isoformat())
        bars[-2]["low"] = 1.0828
        bars[-1] = create_bar(1.0835, 1.0840, 1.0830, 1.0845, base_time.replace(minute=65).isoformat())
        bars[-1]["close"] = 1.0848

        vwap_price = 1.0838
        ms = create_market_state(bars, datetime(2024, 1, 15, 13, 0))
        ms.vwap = vwap_price
        ms.server_time = datetime(2024, 1, 15, 13, 5)

        result = self.strategy.detect_signal(ms)
        assert result is not None
        assert result.side == "buy"
        assert result.setup == "vwap-reversal"

    def test_manage_open_positions_trailing_to_vwap(self):
        position = Position(
            ticket=1,
            magic=50001,
            symbol="EURUSD",
            side="buy",
            volume=0.1,
            price_open=1.0850,
            sl=1.0830,
            tp=1.0890,
            profit=15.0,
            opened_at=datetime.now(),
        )

        bars = []
        base_time = datetime(2024, 1, 15, 9, 0)
        for i in range(20):
            t = base_time.replace(minute=i * 5)
            bars.append(create_bar(1.0850, 1.0860, 1.0845, 1.0855, t.isoformat()))

        vwap_price = 1.0852
        ms = create_market_state(bars, datetime(2024, 1, 15, 9, 30))
        ms.vwap = vwap_price
        ms.open_positions = [position]

        actions = self.strategy.manage_open_positions([position], ms)
        assert len(actions) > 0

    def test_manage_open_positions_breakeven(self):
        position = Position(
            ticket=2,
            magic=50001,
            symbol="EURUSD",
            side="buy",
            volume=0.1,
            price_open=1.0850,
            sl=1.0830,
            tp=1.0890,
            profit=10.0,
            opened_at=datetime.now(),
        )

        bars = []
        base_time = datetime(2024, 1, 15, 9, 0)
        for i in range(20):
            t = base_time.replace(minute=i * 5)
            bars.append(create_bar(1.0850, 1.0860, 1.0845, 1.0855, t.isoformat()))

        ms = create_market_state(bars, datetime(2024, 1, 15, 9, 30))
        ms.vwap = 1.0850
        ms.open_positions = [position]

        actions = self.strategy.manage_open_positions([position], ms)
        be_actions = [a for a in actions if a.op == "modify"]
        assert len(be_actions) > 0

    def test_manage_open_positions_time_stop_outside_killzone(self):
        position = Position(
            ticket=3,
            magic=50001,
            symbol="EURUSD",
            side="buy",
            volume=0.1,
            price_open=1.0850,
            sl=1.0830,
            tp=1.0890,
            profit=5.0,
            opened_at=datetime.now(),
        )

        bars = []
        for i in range(20):
            t = datetime(2024, 1, 15, 9, 0).replace(minute=i * 5)
            bars.append(create_bar(1.0850, 1.0860, 1.0845, 1.0855, t.isoformat()))

        ms = create_market_state(bars, datetime(2024, 1, 15, 12, 30))
        ms.vwap = 1.0855
        ms.open_positions = [position]

        actions = self.strategy.manage_open_positions([position], ms)
        close_actions = [a for a in actions if a.op == "close"]
        assert len(close_actions) > 0

    def test_size_calculation(self):
        ms = MarketState(
            symbol="EURUSD",
            timeframe="M5",
            bid=1.0850,
            ask=1.0851,
            spread_pts=10,
            atr_pts=100,
            bars=[],
            session="london",
            server_time=datetime.now(),
            account_equity=10000,
            account_balance=10000,
        )

        volume = self.strategy._size(ms, 20)
        assert volume > 0
        assert isinstance(volume, float)

    def test_pin_bear_detection(self):
        pin_bar = {
            "open": 1.0850,
            "high": 1.0865,
            "low": 1.0850,
            "close": 1.0852,
        }
        assert self.strategy._is_pin_bear(pin_bar) is True

        normal_bar = {
            "open": 1.0850,
            "high": 1.0860,
            "low": 1.0845,
            "close": 1.0855,
        }
        assert self.strategy._is_pin_bear(normal_bar) is False

    def test_pin_bull_detection(self):
        pin_bar = {
            "open": 1.0852,
            "high": 1.0855,
            "low": 1.0835,
            "close": 1.0838,
        }
        assert self.strategy._is_pin_bull(pin_bar) is True

        normal_bar = {
            "open": 1.0850,
            "high": 1.0860,
            "low": 1.0845,
            "close": 1.0855,
        }
        assert self.strategy._is_pin_bull(normal_bar) is False