from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Literal, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class MarketState(BaseModel):
    symbol: str
    timeframe: Literal["M1","M5","M15","M30","H1","H4","D1"]
    bid: float
    ask: float
    spread_pts: int
    atr_pts: float
    bars: list[dict]
    vwap: Optional[float] = None
    session: Literal["asia","london","ny","off"] = "off"
    server_time: datetime
    account_equity: float
    account_balance: float
    open_positions: list["Position"] = []

class Position(BaseModel):
    ticket: int
    magic: int
    symbol: str
    side: Literal["buy","sell"]
    volume: float
    price_open: float
    sl: float
    tp: float
    profit: float
    opened_at: datetime
    comment: str = ""

class Signal(BaseModel):
    side: Literal["buy","sell"]
    symbol: str
    volume: float
    sl: float
    tp: float
    magic: int
    comment: str = ""
    valid_until: Optional[datetime] = None
    setup: str
    confidence: float = Field(ge=0, le=1)

class Action(BaseModel):
    op: Literal["open","close","modify","partial_close","cancel"]
    payload: dict

class NewsEvent(BaseModel):
    currency: str
    impact: Literal["high","medium","low"]
    time: datetime
    name: str

class BrokerContext(BaseModel):
    open_positions_count: int
    equity_drawdown_pct: float
    daily_drawdown_pct: float
    strategy_capital_used: float