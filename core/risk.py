from dataclasses import dataclass


@dataclass
class RiskParams:
    max_risk_per_trade: float = 0.02
    max_positions: int = 5
    max_drawdown_pct: float = 10.0


class RiskManager:
    def __init__(self, params: RiskParams) -> None:
        self.params = params
        self._open_positions = 0

    def can_open_position(self) -> bool:
        return self._open_positions < self.params.max_positions

    def calculate_lot_size(self, account_balance: float, stop_loss_pips: float) -> float:
        risk_amount = account_balance * self.params.max_risk_per_trade
        return risk_amount / (stop_loss_pips * 10)
