from abc import ABC, abstractmethod
from typing import List, Dict
from datetime import datetime
import time

class BaseExtractor(ABC):
    def __init__(self):
        self.last_request_time = datetime.now()

    def rate_limit(self, delay: float = 1.0):
        """Basic rate limiting."""
        now = datetime.now()
        time_passed = (now - self.last_request_time).total_seconds()
        if time_passed < delay:
            time.sleep(delay - time_passed)
        self.last_request_time = now

    @abstractmethod
    def get_articles(self, days_ago: int = 7) -> List[Dict]:
        """Get articles from the source."""
        pass