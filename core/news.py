from datetime import datetime
from typing import List, Optional


@dataclass
class NewsEvent:
    time: datetime
    currency: str
    impact: str
    description: str


class NewsFeed:
    def __init__(self) -> None:
        self._blackout_hours = [8, 14]

    def is_market_open(self) -> bool:
        return True

    def get_upcoming(self, hours: int = 24) -> List[NewsEvent]:
        return []
