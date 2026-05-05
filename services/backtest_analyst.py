"""
Backtest Analyst - Analyzes MT5 backtest results using AI.
"""

from pathlib import Path
from services.backtest_parser import BacktestReport, parse_backtest
from services.analyst import ModelConfig, create_provider, LLMProvider, AnalysisResult
from loguru import logger

SYSTEM_PROMPT = """You are an expert MT5 MQL5 trading robot analyst. 
Analyze backtest results and provide actionable improvements.
Be specific, technical, and concise. Focus on:
1. Win rate, profit factor, drawdown issues
2. Trade pattern problems (entries, exits, SL/TP)
3. Time-based failures (news, killzones, sessions)
4. Risk management issues
5. Specific MQL5 code improvements

Output structured analysis only."""

TRADES_ANALYSIS_PROMPT = """Analyze these MT5 backtest results:

Symbol: {symbol}
Timeframe: {timeframe}
Period: {start} to {end}
Total Trades: {total_trades}
Win Rate: {win_rate}%
Profit Factor: {profit_factor}
Max Drawdown: {max_dd}%
Initial Deposit: ${deposit}
Final Balance: ${balance}

Trades breakdown:
{trades_table}

Provide:
1. Key issues found
2. Specific improvement suggestions for the MQL5 EA
3. Pattern analysis (when does it fail?)
4. Risk assessment
5. Priority fix list (top 3 actions)
"""

def build_trades_table(trades: list) -> str:
    """Build a compact table of trades for the prompt."""
    lines = ["Ticket | Type | Symbol | Volume | Profit | Pips | Duration(min)"]
    lines.append("--------|------|--------|--------|--------|------|-------------")
    for t in trades[:50]:  # limit for token budget
        lines.append(f"{t.ticket} | {t.type} | {t.symbol} | {t.volume} | ${t.profit:.2f} | {t.pnl_pips:.1f} | {t.duration_minutes:.0f}")
    return "\n".join(lines)

class BacktestAnalyst:
    """Analyzes backtest reports using AI."""
    
    def __init__(self, config: ModelConfig):
        self.provider = create_provider(config)
        self.config = config
    
    def analyze(self, report: BacktestReport) -> AnalysisResult:
        """Run full analysis on a backtest report."""
        logger.info(f"Analyzing {report.total_trades} trades...")
        
        prompt = TRADES_ANALYSIS_PROMPT.format(
            symbol=report.symbol,
            timeframe=report.timeframe,
            start=report.period_start.strftime("%Y-%m-%d"),
            end=report.period_end.strftime("%Y-%m-%d"),
            total_trades=report.total_trades,
            win_rate=report.win_rate,
            profit_factor=report.profit_factor,
            max_dd=report.max_drawdown_pct,
            deposit=report.initial_deposit,
            balance=report.final_balance,
            trades_table=build_trades_table(report.trades)
        )
        
        response = self.provider.complete(prompt, SYSTEM_PROMPT)
        
        # Parse response into structured result
        result = AnalysisResult(
            summary=f"Analyzed {report.total_trades} trades. Win rate: {report.win_rate}%, PF: {report.profit_factor}",
            trades_analyzed=report.total_trades,
            win_rate=report.win_rate,
            profit_factor=report.profit_factor,
            raw_response=response
        )
        
        # Try to extract structured info from response
        result.issues_found = _extract_list(response, ["issue", "problem", "fail"])
        result.suggestions = _extract_list(response, ["suggest", "improve", "change", "fix"])
        
        return result
    
    def analyze_file(self, filepath: str | Path) -> AnalysisResult:
        """Load and analyze a backtest file."""
        report = parse_backtest(filepath)
        return self.analyze(report)

def _extract_list(text: str, keywords: list[str]) -> list[str]:
    """Simple extraction of bullet points from text."""
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        if any(kw in line.lower() for kw in keywords):
            # Remove bullet points, numbers, etc.
            clean = line.lstrip('- *#123456789.').strip()
            if clean:
                lines.append(clean)
    return lines[:10]  # limit results

def quick_analyze(filepath: str, 
                  provider: str = "openai",
                  model: str = "gpt-4",
                  api_key: str = "") -> AnalysisResult:
    """One-command backtest analysis."""
    config = ModelConfig(
        provider=provider,
        model=model,
        api_key=api_key or None
    )
    analyst = BacktestAnalyst(config)
    return analyst.analyze_file(filepath)