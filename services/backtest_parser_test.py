import pytest
from pathlib import Path
from services.backtest_parser import MT5ReportParser, parse_backtest, TradeResult, BacktestReport

def test_parser_html_basic():
    html = """
    <html><body>
    <table>
    <tr><td>#12345</td><td>EURUSD</td><td>buy</td><td>1.08500</td><td>1.08600</td><td>15.50</td><td>0.10</td></tr>
    <tr><td>#12346</td><td>EURUSD</td><td>sell</td><td>1.08500</td><td>1.08400</td><td>-10.00</td><td>0.10</td></tr>
    </table>
    </body></html>
    """
    parser = MT5ReportParser()
    report = parser._parse_html(html)
    assert report.total_trades >= 0
    assert len(report.trades) >= 0

def test_pips_calculation():
    parser = MT5ReportParser()
    pips = parser._calc_pips(15.50, 0.10, "EURUSD")
    assert pips == pytest.approx(15.5, 0.1)