from hn import HN as HackerNews
from datetime import datetime, timedelta
from typing import List, Dict
import time
from .base import BaseExtractor

class HackerNewsExtractor(BaseExtractor):
    def __init__(self, min_score: int = 100):
        super().__init__()
        self.hn = HackerNews()
        self.min_score = min_score

    def get_articles(self, days_ago: int = 7) -> List[Dict]:
        articles = []
        cutoff_time = time.time() - (days_ago * 24 * 60 * 60)
        
        try:
            # Get top stories from HN
            for story in self.hn.get_stories(story_type='top', limit=100):
                self.rate_limit(0.5)  # HN API rate limiting
                
                if (story.submission_time > cutoff_time and 
                    hasattr(story, 'url') and 
                    story.points >= self.min_score):
                    
                    articles.append({
                        "title": story.title,
                        "url": story.url,
                        "source": "HackerNews",
                        "score": story.points,
                        "published_date": datetime.fromtimestamp(story.submission_time).isoformat(),
                        "comment_count": story.num_comments
                    })
        except Exception as e:
            print(f"Error fetching from HackerNews: {e}")

        return articles