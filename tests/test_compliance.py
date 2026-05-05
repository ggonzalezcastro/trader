import pytest
from datetime import datetime, timedelta, timezone
from core.compliance import ComplianceEngine, BROKER_PROFILES, BrokerProfile


class MockContext:
    def __init__(self, **kwargs):
        self.open_positions_count = kwargs.get("open_positions_count", 0)
        self.equity_drawdown_pct = kwargs.get("equity_drawdown_pct", 0)
        self.daily_drawdown_pct = kwargs.get("daily_drawdown_pct", 0)
        self.strategy_capital_used = kwargs.get("strategy_capital_used", 0)
        self.is_news_blackout = lambda sym, mins: False


class MockSignal:
    def __init__(self, setup="test", symbol="EURUSD"):
        self.setup = setup
        self.symbol = symbol


def test_ftmo_quota_exhausted():
    eng = ComplianceEngine("FTMO")
    for _ in range(1800):
        eng.record_server_request()

    can, reason = eng.can_send_signal(MockContext(), MockSignal())
    assert not can
    assert "quota" in reason


def test_ftmo_quota_ok():
    eng = ComplianceEngine("FTMO")
    eng._reqs.clear()
    can, reason = eng.can_send_signal(MockContext(), MockSignal())
    assert can
    assert reason == "ok"


def test_kill_switch_trip():
    eng = ComplianceEngine("FTMO")
    eng.trip("test_reason")

    can, reason = eng.can_send_signal(MockContext(), MockSignal())
    assert not can
    assert "kill-switch" in reason


def test_kill_switch_reset():
    eng = ComplianceEngine("FTMO")
    eng.trip("test_reason")
    eng.reset_kill()

    can, reason = eng.can_send_signal(MockContext(), MockSignal())
    assert can


def test_fundednext_cap_lower_than_ftmo():
    ft = BROKER_PROFILES["FTMO"]
    fn = BROKER_PROFILES["FundedNext"]
    assert fn.max_strategy_capital < ft.max_strategy_capital
    assert fn.max_strategy_capital == 300_000
    assert ft.max_strategy_capital == 400_000


def test_news_blackout_set_clear():
    eng = ComplianceEngine("FTMO")
    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    eng.set_news_blackout(future)

    assert eng._news_blackout_until is not None

    eng.clear_news_blackout()
    assert eng._news_blackout_until is None


def test_quota_gc():
    eng = ComplianceEngine("FTMO")
    old = datetime.now(timezone.utc) - timedelta(days=2)
    eng._reqs.append(old)
    eng._reqs.append(datetime.now(timezone.utc))

    eng._gc_reqs(datetime.now(timezone.utc))
    assert len(eng._reqs) == 1


def test_max_positions():
    eng = ComplianceEngine("FTMO")
    ctx = MockContext(open_positions_count=180)

    can, reason = eng.can_send_signal(ctx, MockSignal())
    assert not can
    assert "max_open_positions" in reason


def test_overall_loss_limit():
    eng = ComplianceEngine("FTMO")
    ctx = MockContext(equity_drawdown_pct=9.1)

    can, reason = eng.can_send_signal(ctx, MockSignal())
    assert not can
    assert "overall_loss" in reason


def test_daily_loss_limit():
    eng = ComplianceEngine("FTMO")
    ctx = MockContext(daily_drawdown_pct=5.0)

    can, reason = eng.can_send_signal(ctx, MockSignal())
    assert not can
    assert "daily_loss" in reason


def test_quota_status():
    eng = ComplianceEngine("FTMO")
    for _ in range(500):
        eng.record_server_request()

    status = eng.get_quota_status()
    assert status["requests_today"] == 500
    assert status["limit"] == 1800
    assert status["pct_used"] == pytest.approx(27.8, 0.1)


def test_generic_broker_high_limit():
    eng = ComplianceEngine("Generic")
    ctx = MockContext(open_positions_count=180)

    can, reason = eng.can_send_signal(ctx, MockSignal())
    assert can


def test_broker_profile_defaults():
    profile = BROKER_PROFILES["FTMO"]
    assert profile.max_daily_server_requests == 1800
    assert profile.news_blackout_minutes == 2
    assert profile.daily_loss_pct_limit == 4.5
    assert profile.overall_loss_pct_limit == 9.0