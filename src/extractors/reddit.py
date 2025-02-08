import praw
from datetime import datetime, timedelta
from typing import List, Dict
from .base import BaseExtractor

class RedditExtractor(BaseExtractor):
    def __init__(self, client_id: str, client_secret: str, subreddits: List[str]):
        super().__init__()
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent="ArticleCurator/1.0"
        )
        self.subreddits = subreddits

    def get_articles(self, days_ago: int = 7) -> List[Dict]:
        articles = []
        
        for subreddit_name in self.subreddits:
            try:
                subreddit = self.reddit.subreddit(subreddit_name)
                for post in subreddit.top(time_filter="week", limit=25):
                    if not post.is_self and not post.stickied:  # External links only
                        articles.append({
                            "title": post.title,
                            "url": post.url,
                            "source": f"Reddit-{subreddit_name}",
                            "score": post.score,
                            "published_date": datetime.fromtimestamp(post.created_utc).isoformat(),
                            "comment_count": post.num_comments,
                            "upvote_ratio": post.upvote_ratio
                        })
            except Exception as e:
                print(f"Error fetching from r/{subreddit_name}: {e}")

        return articles