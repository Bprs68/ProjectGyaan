import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

import trafilatura
from tavily import TavilyClient

logger = logging.getLogger(__name__)


class ContentExtractor:
    def __init__(self):
        self.client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

    def extract_batch(self, urls: List[str], max_workers: int = 2) -> Dict[str, str]:
        """Extract content from URLs in parallel chunks of 5. Returns {url: content}."""
        chunks = [urls[i : i + 5] for i in range(0, len(urls), 5)]
        extracted: Dict[str, str] = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self._extract_chunk, chunk) for chunk in chunks]
            for future in as_completed(futures):
                try:
                    extracted.update(future.result())
                except Exception as e:
                    logger.error(f"Chunk extraction error: {e}")

        return extracted

    def _extract_chunk(self, chunk: List[str]) -> Dict[str, str]:
        result: Dict[str, str] = {}
        try:
            response = self.client.extract(urls=chunk)
            for r in response.get("results", []):
                url = r.get("url", "")
                content = r.get("raw_content", "")
                if url and content:
                    result[url] = content
            # Trafilatura fallback for any URLs Tavily missed
            for url in [u for u in chunk if u not in result]:
                content = self._trafilatura_extract(url)
                if content:
                    result[url] = content
        except Exception as e:
            logger.warning(f"Tavily extract failed for chunk, falling back: {e}")
            for url in chunk:
                content = self._trafilatura_extract(url)
                if content:
                    result[url] = content
        return result

    def _trafilatura_extract(self, url: str) -> Optional[str]:
        try:
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                return trafilatura.extract(
                    downloaded,
                    include_links=False,
                    include_images=False,
                    favor_precision=True,
                )
        except Exception as e:
            logger.debug(f"Trafilatura failed for {url}: {e}")
        return None
