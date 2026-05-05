from datetime import datetime, timedelta, timezone
from collections import deque
from typing import Literal
from pydantic import BaseModel

class BrokerProfile(BaseModel):
    broker_id: Literal["FTMO", "FundedNext", "The5ers", "MyFundedFX", "Generic"]
    max_daily_server_requests: int = 1800
    max_open_positions: int = 180
    news_blackout_minutes: int = 2
    max_strategy_capital: float = 400_000
    forbid_hedging_across_accounts: bool = True
    forbid_hft_seconds: int = 30
    daily_loss_pct_limit: float = 4.5
    overall_loss_pct_limit: float = 9.0

BROKER_PROFILES = {
    "FTMO": BrokerProfile(
        broker_id="FTMO",
        max_daily_server_requests=1800,
        max_open_positions=180,
        news_blackout_minutes=2,
        max_strategy_capital=400_000,
        forbid_hedging_across_accounts=True,
        forbid_hft_seconds=30,
        daily_loss_pct_limit=4.5,
        overall_loss_pct_limit=9.0,
    ),
    "FundedNext": BrokerProfile(
        broker_id="FundedNext",
        max_daily_server_requests=1800,
        max_open_positions=180,
        news_blackout_minutes=2,
        max_strategy_capital=300_000,
        forbid_hedging_across_accounts=True,
        forbid_hft_seconds=30,
        daily_loss_pct_limit=5.0,
        overall_loss_pct_limit=10.0,
    ),
    "Generic": BrokerProfile(
        broker_id="Generic",
        max_daily_server_requests=10000,
        max_open_positions=200,
        news_blackout_minutes=5,
        max_strategy_capital=1_000_000,
        forbid_hedging_across_accounts=False,
        forbid_hft_seconds=10,
        daily_loss_pct_limit=5.0,
        overall_loss_pct_limit=10.0,
    ),
}

class ComplianceEngine:
    def __init__(self, broker_id: str = "FTMO"):
        self.profile = BROKER_PROFILES.get(broker_id, BROKER_PROFILES["Generic"])
        self._reqs: deque[datetime] = deque()
        self._kill = False
        self._kill_reason = ""
        self._news_blackout_until: datetime | None = None

    def _gc_reqs(self, now: datetime) -> None:
        cutoff = now - timedelta(days=1)
        while self._reqs and self._reqs[0] < cutoff:
            self._reqs.popleft()

    def record_server_request(self) -> None:
        now = datetime.now(timezone.utc)
        self._gc_reqs(now)
        self._reqs.append(now)

    def can_send_signal(self, ctx: "BrokerContext", signal: "Signal") -> tuple[bool, str]:
        if self._kill:
            return False, f"kill-switch: {self._kill_reason}"

        now = datetime.now(timezone.utc)
        self._gc_reqs(now)

        if len(self._reqs) >= self.profile.max_daily_server_requests:
            return False, "server_request_quota_exhausted"

        if ctx.open_positions_count >= self.profile.max_open_positions:
            return False, "max_open_positions"

        if ctx.equity_drawdown_pct >= self.profile.overall_loss_pct_limit:
            self.trip("overall_loss_limit")
            return False, "overall_loss_limit_exceeded"

        if ctx.daily_drawdown_pct >= self.profile.daily_loss_pct_limit:
            self.trip("daily_loss_limit")
            return False, "daily_loss_limit_exceeded"

        if self._news_blackout_until and now < self._news_blackout_until:
            return False, "news_blackout_active"

        if ctx.strategy_capital_used >= self.profile.max_strategy_capital:
            return False, "strategy_capital_cap_exceeded"

        return True, "ok"

    def trip(self, reason: str) -> None:
        self._kill = True
        self._kill_reason = reason

    def reset_kill(self) -> None:
        self._kill = False
        self._kill_reason = ""

    def set_news_blackout(self, until: datetime) -> None:
        self._news_blackout_until = until

    def clear_news_blackout(self) -> None:
        self._news_blackout_until = None

    def get_quota_status(self) -> dict:
        now = datetime.now(timezone.utc)
        self._gc_reqs(now)
        return {
            "requests_today": len(self._reqs),
            "limit": self.profile.max_daily_server_requests,
            "pct_used": round(len(self._reqs) / self.profile.max_daily_server_requests * 100, 1),
        }