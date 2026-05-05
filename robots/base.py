from abc import ABC, abstractmethod
from typing import Optional
from core.types import MarketState, Signal, Action, NewsEvent, Position

class Robot(ABC):
    name: str = "unnamed"
    version: str = "0.0.1"
    magic: int = 0
    symbols: list[str] = []
    timeframes: list[str] = []
    broker_compat: list[str] = []

    @abstractmethod
    def detect_signal(self, ms: MarketState) -> Optional[Signal]:
        pass

    @abstractmethod
    def manage_open_positions(self, positions: list[Position], ms: MarketState) -> list[Action]:
        pass

    def on_news_event(self, event: NewsEvent) -> list[Action]:
        return []

    def on_session_change(self, prev: str, new: str) -> list[Action]:
        return []

    def on_position_opened(self, pos: Position) -> None:
        pass

    def on_position_closed(self, pos: Position, reason: str) -> None:
        pass