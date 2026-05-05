import pytest
from datetime import datetime, timezone, timedelta
from core.compliance import ComplianceEngine, BROKER_PROFILES, BrokerProfile

class MockContext:
    def __init__(self,
                 open_positions_count: int = 0,
                 equity_drawdown_pct: float = 0.0,
                 daily_drawdown_pct: float = 0.0,
                 strategy_capital_used: float = 0.0):
        self.open_positions_count = open_positions_count
        self.equity_drawdown_pct = equity_drawdown_pct
        self.daily_drawdown_pct = daily_drawdown_pct
        self.strategy_capital_used = strategy_capital_used

class MockSignal:
    pass

def test_ftmo_quota_exhausted():
    eng = ComplianceEngine("FTMO")
    for _ in range(1800):
        eng.record_server_request()
    can, reason = eng.can_send_signal(MockContext(), MockSignal())
    assert not can
    assert "quota" in reason

def test_kill_switch_trip():
    eng = ComplianceEngine("FTMO")
    eng.trip("test_reason")
    can, reason = eng.can_send_signal(MockContext(), MockSignal())
    assert not can
    assert "kill-switch" in reason

def test_fundednext_cap_lower():
    ft = BROKER_PROFILES["FTMO"]
    fn = BROKER_PROFILES["FundedNext"]
    assert fn.max_strategy_capital < ft.max_strategy_capital

def test_generic_broker_allows_hedging():
    gen = BROKER_PROFILES["Generic"]
    assert gen.forbid_hedging_across_accounts is False

def test_max_open_positions():
    eng = ComplianceEngine("FTMO")
    ctx = MockContext(open_positions_count=180)
    can, reason = eng.can_send_signal(ctx, MockSignal())
    assert not can
    assert "max_open_positions" in reason

def test_overall_loss_limit_trips_kill():
    eng = ComplianceEngine("FTMO")
    ctx = MockContext(equity_drawdown_pct=9.5)
    can, reason = eng.can_send_signal(ctx, MockSignal())
    assert not can
    assert "overall_loss_limit_exceeded" in reason
    assert eng._kill is True
    assert eng._kill_reason == "overall_loss_limit"

def test_daily_loss_limit_trips_kill():
    eng = ComplianceEngine("FTMO")
    ctx = MockContext(daily_drawdown_pct=5.0)
    can, reason = eng.can_send_signal(ctx, MockSignal())
    assert not can
    assert "daily_loss_limit_exceeded" in reason
    assert eng._kill is True
    assert eng._kill_reason == "daily_loss_limit"

def test_news_blackout_active():
    eng = ComplianceEngine("FTMO")
    eng.set_news_blackout(datetime.now(timezone.utc) + timedelta(hours=1))
    ctx = MockContext()
    can, reason = eng.can_send_signal(ctx, MockSignal())
    assert not can
    assert "news_blackout_active" in reason

def test_news_blackout_cleared():
    eng = ComplianceEngine("FTMO")
    eng.set_news_blackout(datetime.now(timezone.utc) - timedelta(hours=1))
    ctx = MockContext()
    can, reason = eng.can_send_signal(ctx, MockSignal())
    assert can
    assert reason == "ok"

def test_strategy_capital_exceeded():
    eng = ComplianceEngine("FTMO")
    ctx = MockContext(strategy_capital_used=400_001)
    can, reason = eng.can_send_signal(ctx, MockSignal())
    assert not can
    assert "strategy_capital_cap_exceeded" in reason

def test_reset_kill_switch():
    eng = ComplianceEngine("FTMO")
    eng.trip("test_reason")
    assert eng._kill is True
    eng.reset_kill()
    assert eng._kill is False
    assert eng._kill_reason == ""

def test_quota_status():
    eng = ComplianceEngine("FTMO")
    for _ in range(100):
        eng.record_server_request()
    status = eng.get_quota_status()
    assert status["requests_today"] == 100
    assert status["limit"] == 1800
    assert status["pct_used"] == 5.6

def test_gc_clears_old_requests():
    eng = ComplianceEngine("FTMO")
    old_time = datetime.now(timezone.utc) - timedelta(days=2)
    eng._reqs.append(old_time)
    eng.record_server_request()
    status = eng.get_quota_status()
    assert status["requests_today"] == 1

def test_unknown_broker_defaults_to_generic():
    eng = ComplianceEngine("UnknownBroker")
    assert eng.profile.broker_id == "Generic"
    assert eng.profile.max_daily_server_requests == 10000