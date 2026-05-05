"""
Parses MT5 Strategy Tester export files (HTML/XML/CSV) into structured trade data.
Model-agnostic output for AI consumption.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal
import re

@dataclass
class TradeResult:
    ticket: int
    symbol: str
    type: Literal["buy", "sell"]
    volume: float
    open_time: datetime
    close_time: datetime
    open_price: float
    close_price: float
    sl: float
    tp: float
    profit: float
    commission: float
    magic: int
    comment: str

    pnl_pips: float
    duration_minutes: float
    rr_ratio: float | None
    was_successful: bool | None

@dataclass
class BacktestReport:
    symbol: str
    timeframe: str
    period_start: datetime
    period_end: datetime
    initial_deposit: float
    final_balance: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float | None
    trades: list[TradeResult]

    def to_dict(self) -> dict:
        return asdict(self)

class MT5ReportParser:

    def parse_file(self, filepath: Path) -> BacktestReport:
        content = filepath.read_text(encoding="utf-8", errors="ignore")

        if filepath.suffix.lower() == ".html":
            return self._parse_html(content)
        elif filepath.suffix.lower() == ".xml":
            return self._parse_xml(content)
        elif filepath.suffix.lower() in [".csv", ".txt"]:
            return self._parse_csv(content)
        else:
            raise ValueError(f"Unsupported file format: {filepath.suffix}")

    def _parse_html(self, content: str) -> BacktestReport:
        trades = self._extract_trades_from_html(content)
        summary = self._extract_summary_from_html(content)

        return BacktestReport(
            symbol=summary.get("symbol", "UNKNOWN"),
            timeframe=summary.get("timeframe", "M5"),
            period_start=summary.get("start", datetime.now()),
            period_end=summary.get("end", datetime.now()),
            initial_deposit=summary.get("deposit", 10000),
            final_balance=summary.get("balance", 10000),
            total_trades=summary.get("trades", 0),
            winning_trades=summary.get("winners", 0),
            losing_trades=summary.get("losers", 0),
            win_rate=summary.get("win_rate", 0),
            profit_factor=summary.get("profit_factor", 0),
            max_drawdown_pct=summary.get("max_dd", 0),
            sharpe_ratio=summary.get("sharpe"),
            trades=trades
        )

    def _extract_trades_from_html(self, content: str) -> list[TradeResult]:
        trades = []
        rows = re.findall(r'<tr[^>]*class="[^"]*deals[^"]*"[^>]*>(.*?)</tr>', content, re.DOTALL | re.IGNORECASE)
        if not rows:
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', content, re.DOTALL | re.IGNORECASE)

        ticket_pattern = r'#(\d+)'

        for i, row in enumerate(rows[:200]):
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL | re.IGNORECASE)
            if len(cells) < 8:
                continue

            try:
                ticket_match = re.search(ticket_pattern, cells[0])
                if not ticket_match:
                    continue

                ticket = int(ticket_match.group(1))
                symbol = self._clean_html(cells[1]) if len(cells) > 1 else "UNKNOWN"
                type_str = self._clean_html(cells[2]).lower() if len(cells) > 2 else "buy"
                type_ = "buy" if "buy" in type_str or "long" in type_str else "sell"

                open_price = self._extract_number(cells[3] if len(cells) > 3 else "")
                close_price = self._extract_number(cells[4] if len(cells) > 4 else "")
                profit = self._extract_number(cells[5] if len(cells) > 5 else "")
                volume = self._extract_number(cells[6] if len(cells) > 6 else "")

                pnl_pips = self._calc_pips(profit, volume, symbol)
                duration = 0

                trade = TradeResult(
                    ticket=ticket,
                    symbol=symbol,
                    type=type_,
                    volume=volume,
                    open_time=datetime.now(),
                    close_time=datetime.now(),
                    open_price=open_price,
                    close_price=close_price,
                    sl=0,
                    tp=0,
                    profit=profit,
                    commission=0,
                    magic=0,
                    comment="",
                    pnl_pips=pnl_pips,
                    duration_minutes=duration,
                    rr_ratio=None,
                    was_successful=None
                )
                trades.append(trade)
            except Exception:
                continue

        return trades

    def _extract_summary_from_html(self, content: str) -> dict:
        summary = {}

        patterns = {
            "symbol": r'Symbol:</td><td[^>]*>([^<]+)</td>',
            "timeframe": r'Timeframe:</td><td[^>]*>([^<]+)</td>',
            "deposit": r'Initial Deposit.*?(\d+\.?\d*)',
            "balance": r'Balance.*?(\d+\.?\d*)',
            "trades": r'Total Trades.*?(\d+)',
            "winners": r'Winner.*?(\d+)',
            "losers": r'Loser.*?(\d+)',
            "profit_factor": r'Profit Factor.*?(\d+\.?\d*)',
            "max_dd": r'Max Drawdown.*?(\d+\.?\d*)%',
            "win_rate": r'Win Rate.*?(\d+\.?\d*)%',
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                val = match.group(1).strip()
                if key in ["deposit", "balance", "profit_factor", "max_dd"]:
                    try:
                        summary[key] = float(val)
                    except:
                        summary[key] = val
                elif key in ["trades", "winners", "losers"]:
                    try:
                        summary[key] = int(val)
                    except:
                        summary[key] = val
                else:
                    summary[key] = val

        if "winners" in summary and "losers" in summary:
            total = summary.get("winners", 0) + summary.get("losers", 0)
            if total > 0:
                summary["win_rate"] = round(summary["winners"] / total * 100, 2)

        return summary

    def _clean_html(self, text: str) -> str:
        return re.sub(r'<[^>]+>', '', text).strip()

    def _extract_number(self, text: str) -> float:
        text = self._clean_html(text)
        match = re.search(r'[-+]?\d+\.?\d*', text.replace(',', ''))
        return float(match.group()) if match else 0.0

    def _calc_pips(self, profit: float, volume: float, symbol: str) -> float:
        if volume == 0:
            return 0.0
        pip_value = 10.0 * volume
        if profit == 0:
            return 0.0
        return round(profit / pip_value, 1)

    def _parse_xml(self, content: str) -> BacktestReport:
        return self._parse_html(content)

    def _parse_csv(self, content: str) -> BacktestReport:
        lines = content.strip().split('\n')
        trades = []
        for line in lines[1:]:
            parts = line.split(',')
            if len(parts) >= 8:
                try:
                    trade = TradeResult(
                        ticket=int(parts[0]),
                        symbol=parts[1],
                        type="buy" if "buy" in parts[2].lower() else "sell",
                        volume=float(parts[3]),
                        open_time=datetime.fromisoformat(parts[4].strip()),
                        close_time=datetime.fromisoformat(parts[5].strip()),
                        open_price=float(parts[6]),
                        close_price=float(parts[7]),
                        sl=float(parts[8]) if len(parts) > 8 else 0,
                        tp=float(parts[9]) if len(parts) > 9 else 0,
                        profit=float(parts[10]) if len(parts) > 10 else 0,
                        commission=float(parts[11]) if len(parts) > 11 else 0,
                        magic=int(parts[12]) if len(parts) > 12 else 0,
                        comment=parts[13] if len(parts) > 13 else "",
                        pnl_pips=0,
                        duration_minutes=0,
                        rr_ratio=None,
                        was_successful=None
                    )
                    trades.append(trade)
                except Exception:
                    continue

        return BacktestReport(
            symbol="UNKNOWN", timeframe="M5",
            period_start=datetime.now(), period_end=datetime.now(),
            initial_deposit=10000, final_balance=10000,
            total_trades=len(trades),
            winning_trades=sum(1 for t in trades if t.profit > 0),
            losing_trades=sum(1 for t in trades if t.profit <= 0),
            win_rate=0, profit_factor=0, max_drawdown_pct=0, sharpe_ratio=None,
            trades=trades
        )

def parse_backtest(filepath: str | Path) -> BacktestReport:
    """Main entry point."""
    parser = MT5ReportParser()
    return parser.parse_file(Path(filepath))