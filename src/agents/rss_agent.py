import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from urllib.parse import quote

import feedparser

from src.agents.discovery import _is_non_article_url

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
)
_HTML_TAG = re.compile(r"<[^>]+>")
MAX_AGE_DAYS = 7


class RSSAgent:
    def fetch_topic(
        self,
        topic_id: int,
        topic_name: str,
        feed_urls: List[str],
        max_per_feed: int = 5,
    ) -> List[Dict[str, Any]]:
        """Fetch all RSS feeds + Google News for a topic in parallel."""
        seen_urls: set = set()
        all_results: List[Dict[str, Any]] = []

        google_url = GOOGLE_NEWS_RSS.format(query=quote(topic_name))
        all_feed_urls = list(feed_urls) + [google_url]

        with ThreadPoolExecutor(max_workers=min(6, len(all_feed_urls))) as executor:
            futures = {
                executor.submit(
                    self._fetch_feed, url, topic_id, topic_name, max_per_feed
                ): url
                for url in all_feed_urls
            }
            for future in as_completed(futures):
                try:
                    for result in future.result():
                        if result["url"] not in seen_urls:
                            seen_urls.add(result["url"])
                            all_results.append(result)
                except Exception as e:
                    logger.error(
                        f"Feed failed for topic '{topic_name}' ({futures[future][:60]}): {e}"
                    )

        logger.info(
            f"RSS [{topic_name}]: {len(all_results)} articles from "
            f"{len(feed_urls)} feeds + Google News"
        )
        return all_results

    def _fetch_feed(
        self,
        feed_url: str,
        topic_id: int,
        topic_name: str,
        max_per_feed: int,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
        is_google_news = "news.google.com" in feed_url

        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                if len(results) >= max_per_feed:
                    break

                url = entry.get("link", "")
                if not url:
                    continue

                # Google News wraps real URLs in a redirect — skip; Tavily extractor
                # can follow the redirect, but we flag them so they're not treated
                # as a resolved domain in `source`.
                if is_google_news and "news.google.com" in url:
                    # Try to find the real URL in the entry source
                    real = (entry.get("source") or {}).get("href", url)
                    if "news.google.com" in real:
                        real = url  # keep redirect, extractor will resolve
                    url = real

                if _is_non_article_url(url):
                    continue

                # Age filter — skip if published date is available but too old
                pub_struct = entry.get("published_parsed") or entry.get("updated_parsed")
                if pub_struct:
                    try:
                        pub_dt = datetime(*pub_struct[:6], tzinfo=timezone.utc)
                        if pub_dt < cutoff:
                            continue
                    except Exception:
                        pass  # malformed date — include anyway

                # Clean up snippet
                raw_snippet = ""
                if entry.get("summary"):
                    raw_snippet = entry.summary
                elif entry.get("content"):
                    raw_snippet = entry.content[0].get("value", "")
                snippet = _HTML_TAG.sub("", raw_snippet).strip()[:500]

                domain = url.split("/")[2] if url.startswith("http") else ""
                results.append(
                    {
                        "url": url,
                        "title": entry.get("title", "Untitled"),
                        "snippet": snippet,
                        "source": domain,
                        # RSS from curated feeds is pre-filtered; score high enough
                        # to pass the >0.5 filter in extract_content
                        "relevance_score": 0.72,
                        "topic_name": topic_name,
                        "topic_id": topic_id,
                        "query": f"rss:{feed_url[:50]}",
                    }
                )
        except Exception as e:
            logger.error(f"feedparser error for '{feed_url[:60]}': {e}")

        return results
