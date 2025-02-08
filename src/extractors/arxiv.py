# src/extractors/arxiv.py
import arxiv
from datetime import datetime, timedelta, timezone
from typing import List, Dict
from .base import BaseExtractor

class ArxivExtractor(BaseExtractor):
    def __init__(self, categories: List[str]):
        super().__init__()
        self.categories = categories

    def get_articles(self, days_ago: int = 7) -> List[Dict]:
        articles = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_ago)
        
        query = " OR ".join([f"cat:{cat}" for cat in self.categories])
        search = arxiv.Search(
            query=query,
            max_results=100,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )

        try:
            for result in search.results():
                if result.published > cutoff_date:
                    # Instead of PDF URL, use the abstract page URL
                    article_url = result.entry_id.replace('/abs/', '/pdf/') if '/abs/' in result.entry_id else result.pdf_url
                    
                    articles.append({
                        "title": result.title,
                        "url": article_url,
                        "source": "arXiv",
                        "category": result.primary_category,
                        "published_date": result.published.isoformat(),
                        "authors": [author.name for author in result.authors],
                        "abstract": result.summary,
                        # Include the content directly in the article
                        "content": f"""Title: {result.title}\n\nAuthors: {', '.join(author.name for author in result.authors)}\n\nAbstract: {result.summary}\n\nCategory: {result.primary_category}\n\nPublished: {result.published.strftime('%Y-%m-%d')}"""
                    })
        except Exception as e:
            print(f"Error fetching from arXiv: {e}")

        return articles