import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

import requests
from tavily import TavilyClient

logger = logging.getLogger(__name__)

# Domains that primarily serve PDFs, datasets, or academic repository pages
_EXCLUDED_DOMAINS = [
    "apps.dtic.mil",
    "dspacedirect.org",
    "documents1.worldbank.org",
    "elibrary.worldbank.org",
    "publications.worldbank.org",
    "files.eric.ed.gov",
    "core.ac.uk",
    "semanticscholar.org",
    "jstor.org",
    "researchgate.net",
    "academia.edu",
    "arxiv.org",
    "ssrn.com",
    "nber.org",
    "bis.org",
    "oecd.org",
    "imf.org",
    "un.org",
    "rand.org",
]


def _is_non_article_url(url: str) -> bool:
    """Return True for URLs that are documents/files rather than web articles."""
    u = url.lower()
    return (
        u.endswith(".pdf")
        or u.endswith(".doc")
        or u.endswith(".docx")
        or "/pdf/" in u
        or "/bitstreams/" in u
        or "/dam/" in u
        or u.endswith("/download")
        or "/sti/trecms/" in u
    )


class DiscoveryAgent:
    def __init__(self):
        self.client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

    def search_topic(
        self,
        topic_name: str,
        queries: List[str],
        max_per_query: int = 5,
        max_workers: int = 2,
    ) -> List[Dict[str, Any]]:
        """Search Tavily (general + news) and Hacker News for a topic in parallel."""
        seen_urls: set = set()
        all_results: List[Dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=max_workers + 2) as executor:
            # Tavily general queries
            futures = {
                executor.submit(self._search_query, query, topic_name, max_per_query): query
                for query in queries
            }
            # Tavily news mode — today's coverage per topic
            news_future = executor.submit(self._search_news, topic_name, max_per_query)
            # HN topic search
            hn_future = executor.submit(self._search_hackernews, topic_name)

            for future in as_completed(list(futures.keys()) + [news_future, hn_future]):
                try:
                    for result in future.result():
                        if result["url"] not in seen_urls:
                            seen_urls.add(result["url"])
                            all_results.append(result)
                except Exception as e:
                    label = futures.get(future, "news/HN")
                    logger.error(f"Query future failed for topic '{topic_name}' ({label}): {e}")

        all_results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return all_results

    def get_hn_frontpage(
        self, topics: List[Dict[str, Any]], max_results: int = 50, min_points: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Fetch live HN front-page stories and match each to a topic by keyword.
        Topics is a list of {"id": int, "name": str, "queries": list[str]}.
        Stories that don't match any topic are discarded.
        """
        results: List[Dict[str, Any]] = []
        try:
            resp = requests.get(
                "https://hn.algolia.com/api/v1/search",
                params={
                    "tags": "front_page",
                    "hitsPerPage": max_results,
                    "numericFilters": f"points>{min_points}",
                },
                timeout=10,
            )
            resp.raise_for_status()

            # Build keyword sets per topic from name + query words
            topic_keywords: List[tuple] = []
            for t in topics:
                words = set(t["name"].lower().split())
                for q in t.get("queries", []):
                    words.update(w.lower() for w in q.split() if len(w) > 4)
                topic_keywords.append((t["id"], t["name"], words))

            for hit in resp.json().get("hits", []):
                url = hit.get("url", "")
                if not url or _is_non_article_url(url):
                    continue
                title_lower = hit.get("title", "").lower()
                matched_topic_id = None
                matched_topic_name = None
                for tid, tname, keywords in topic_keywords:
                    if any(kw in title_lower for kw in keywords):
                        matched_topic_id = tid
                        matched_topic_name = tname
                        break
                if matched_topic_id is None:
                    continue

                points = hit.get("points", 0) or 0
                domain = url.split("/")[2] if url.startswith("http") else ""
                relevance = min(1.0, 0.5 + (points - min_points) / (500 - min_points) * 0.5)
                results.append(
                    {
                        "url": url,
                        "title": hit.get("title", "Untitled"),
                        "snippet": "",
                        "source": domain,
                        "relevance_score": relevance,
                        "topic_name": matched_topic_name,
                        "topic_id": matched_topic_id,
                        "query": "HN:front_page",
                    }
                )
        except Exception as e:
            logger.error(f"HN front page fetch error: {e}")
        logger.info(f"HN front page: {len(results)} matched stories")
        return results

    def _search_query(
        self, query: str, topic_name: str, max_per_query: int
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        try:
            response = self.client.search(
                query=query,
                search_depth="advanced",
                max_results=max_per_query,
                topic="general",
                include_answer=False,
                include_raw_content=False,
                exclude_domains=_EXCLUDED_DOMAINS,
            )
            for r in response.get("results", []):
                url = r.get("url", "")
                score = r.get("score", 0)
                if not url or score < 0.4 or _is_non_article_url(url):
                    continue
                domain = url.split("/")[2] if url.startswith("http") else ""
                results.append(
                    {
                        "url": url,
                        "title": r.get("title", "Untitled"),
                        "snippet": r.get("content", ""),
                        "source": domain,
                        "relevance_score": score,
                        "topic_name": topic_name,
                        "query": query,
                    }
                )
        except Exception as e:
            logger.error(f"Tavily search error for '{query}': {e}")
        return results

    def _search_news(
        self, topic_name: str, max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Tavily news-mode search — returns articles published in the last 2 days."""
        results: List[Dict[str, Any]] = []
        try:
            response = self.client.search(
                query=topic_name,
                search_depth="basic",
                max_results=max_results,
                topic="news",
                days=2,
                include_answer=False,
                include_raw_content=False,
                exclude_domains=_EXCLUDED_DOMAINS,
            )
            for r in response.get("results", []):
                url = r.get("url", "")
                score = r.get("score", 0)
                if not url or score < 0.4 or _is_non_article_url(url):
                    continue
                domain = url.split("/")[2] if url.startswith("http") else ""
                results.append(
                    {
                        "url": url,
                        "title": r.get("title", "Untitled"),
                        "snippet": r.get("content", ""),
                        "source": domain,
                        "relevance_score": score,
                        "topic_name": topic_name,
                        "query": f"news:{topic_name}",
                    }
                )
        except Exception as e:
            logger.error(f"Tavily news search error for '{topic_name}': {e}")
        return results

    def _search_hackernews(
        self, topic_name: str, max_results: int = 10, min_points: int = 75
    ) -> List[Dict[str, Any]]:
        """Fetch top Hacker News stories for a topic via the Algolia API."""
        results: List[Dict[str, Any]] = []
        try:
            resp = requests.get(
                "https://hn.algolia.com/api/v1/search",
                params={
                    "query": topic_name,
                    "tags": "story",
                    "hitsPerPage": max_results,
                    "numericFilters": f"points>{min_points}",
                },
                timeout=10,
            )
            resp.raise_for_status()
            for hit in resp.json().get("hits", []):
                url = hit.get("url", "")
                if not url or _is_non_article_url(url):
                    continue
                points = hit.get("points", 0) or 0
                domain = url.split("/")[2] if url.startswith("http") else ""
                # Normalize: 75 pts → 0.5, 500+ pts → 1.0
                relevance = min(1.0, 0.5 + (points - min_points) / (500 - min_points) * 0.5)
                results.append(
                    {
                        "url": url,
                        "title": hit.get("title", "Untitled"),
                        "snippet": "",
                        "source": domain,
                        "relevance_score": relevance,
                        "topic_name": topic_name,
                        "query": f"HN:{topic_name}",
                    }
                )
        except Exception as e:
            logger.error(f"HN search error for '{topic_name}': {e}")
        return results
