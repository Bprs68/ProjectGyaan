# src/extractors/rss.py
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict
import time
from .base import BaseExtractor
import requests
from urllib.parse import urlparse

class RSSExtractor(BaseExtractor):
    def __init__(self, feeds_config: Dict[str, str]):
        super().__init__()
        self.feeds = feeds_config
        
        # Configure headers to mimic a browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def parse_date(self, entry) -> datetime:
        """Parse publication date from feed entry."""
        if hasattr(entry, 'published_parsed'):
            return datetime(*entry.published_parsed[:6])
        elif hasattr(entry, 'updated_parsed'):
            return datetime(*entry.updated_parsed[:6])
        return datetime.now()

    def is_paywall_site(self, url: str) -> bool:
        """Check if the URL is from a known paywall site."""
        paywall_domains = {
            'nature.com',
            'science.org',
            'sciencemag.org',
            'cell.com',
            'nejm.org',
            'ieee.org'
        }
        domain = urlparse(url).netloc.lower()
        return any(pd in domain for pd in paywall_domains)

    def get_articles(self, days_ago: int = 7) -> List[Dict]:
        articles = []
        cutoff_date = datetime.now() - timedelta(days=days_ago)

        for source, feed_url in self.feeds.items():
            try:
                self.rate_limit()
                
                # Use headers for feed fetching
                response = requests.get(feed_url, headers=self.headers, timeout=10)
                feed = feedparser.parse(response.text)
                
                for entry in feed.entries:
                    pub_date = self.parse_date(entry)
                    
                    if pub_date > cutoff_date:
                        # Extract description and handle potential paywall
                        description = entry.get('summary', '')
                        if len(description) < 100 and self.is_paywall_site(entry.link):
                            description = "[This article is from a paywalled source. Full content may not be accessible.]"
                        
                        articles.append({
                            "title": entry.title,
                            "url": entry.link,
                            "source": source,
                            "published_date": pub_date.isoformat(),
                            "description": description,
                            "is_paywalled": self.is_paywall_site(entry.link)
                        })
            except Exception as e:
                print(f"Error fetching {source} feed: {e}")
                continue

        return articles