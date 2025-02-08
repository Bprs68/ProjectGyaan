# src/curator.py
import google.generativeai as genai
from typing import List, Dict
import time
from datetime import datetime
import requests
import trafilatura
import json
from .extractors import RSSExtractor, RedditExtractor, ArxivExtractor, HackerNewsExtractor

class EnhancedArticleCurator:
    # RSS feed URLs remain the same...
    PUBLICATION_FEEDS = {
        'nature': 'https://www.nature.com/nature.rss',
        'science': 'https://www.science.org/rss/news_current.xml',
        'mit_tech': 'https://www.technologyreview.com/feed/',
        'atlantic': 'https://www.theatlantic.com/feed/all/',
        'brookings': 'https://www.brookings.edu/feed/',
        'hbr': 'https://hbr.org/rss/articles',
        'foreign_affairs': 'https://www.foreignaffairs.com/rss.xml',
        'marginal_revolution': 'https://marginalrevolution.com/feed',
        'astral_codex': 'https://astralcodexten.substack.com/feed',
        'stratechery': 'https://stratechery.com/feed/',
        'nber': 'https://www.nber.org/feed/working-papers',
        'distill': 'https://distill.pub/rss.xml',
    }

    REDDIT_SUBREDDITS = [
        "DepthHub", "TrueReddit", "Foodforthought", "Philosophy",
        "Economics", "Science", "AskHistorians", "NeutralPolitics"
    ]

    ARXIV_CATEGORIES = ["cs.AI", "cs.CL", "q-fin", "physics"]

    def __init__(self, gemini_api_key: str, reddit_client_id: str, reddit_client_secret: str):
        # Initialize Gemini
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')

        # Initialize extractors
        self.rss_extractor = RSSExtractor(self.PUBLICATION_FEEDS)
        self.reddit_extractor = RedditExtractor(
            reddit_client_id, 
            reddit_client_secret,
            self.REDDIT_SUBREDDITS
        )
        self.arxiv_extractor = ArxivExtractor(self.ARXIV_CATEGORIES)
        self.hn_extractor = HackerNewsExtractor(min_score=100)

    def extract_article_content(self, url: str, source: str = None, article_data: Dict = None) -> str:
            """Extract the main content from an article URL or use provided content."""
            # If it's an arXiv paper, use the abstract and metadata
            if source == "arXiv" and article_data and "content" in article_data:
                return article_data["content"]
                
            if article_data and article_data.get("is_paywalled", False):
                return "[Content not fully accessible due to paywall]"
                
            try:
                downloaded = trafilatura.fetch_url(url)
                if downloaded:
                    text = trafilatura.extract(downloaded, 
                                            include_links=False, 
                                            include_images=False, 
                                            include_tables=False,
                                            favor_precision=True)
                    return text if text else ""
                return ""
            except Exception as e:
                print(f"Error extracting content from {url}: {e}")
                return ""

    # def evaluate_article(self, title: str, content: str, source: str, is_paywalled: bool = False) -> Dict:
    #         """Use Gemini to evaluate the article's impact and worth."""
    #         prompt = f"""You are an expert article curator. Your task is to evaluate this article and provide a structured analysis.

    # Article Details:
    # Source: {source}
    # Title: {title}
    # Paywall Status: {"Paywalled" if is_paywalled else "Free"}

    # Content: {content[:10000]}...

    # Note: {"This is a paywalled article and evaluation is based on available abstract/summary only" if is_paywalled else "This is the full article content"}.

    # Evaluate this based on:
    # 1. Intellectual depth and rigor
    # 2. Novelty of insights
    # 3. Potential long-term significance
    # 4. Quality of argumentation
    # 5. Practical implications
    # 6. Citation of sources and evidence
    # 7. Unique perspective or analysis

    # Structure your response EXACTLY like this JSON, with nothing else before or after:
    # {{
    #     "impact_score": 7,
    #     "worth_reading": true,
    #     "key_insights": ["First key insight", "Second key insight", "Third key insight"],
    #     "originality_score": 8,
    #     "evidence_quality": 7,
    #     "target_audience": "Description of target audience",
    #     "estimated_reading_time": 15,
    #     "time_value_assessment": "Clear explanation of time value",
    #     "confidence_in_evaluation": 8
    # }}"""

    #         try:
    #             # Generate response from Gemini
    #             response = self.model.generate_content(prompt)
                
    #             # Clean the response text
    #             response_text = response.text.strip()
                
    #             # Remove any markdown code block indicators if present
    #             if response_text.startswith('```json'):
    #                 response_text = response_text[7:]
    #             if response_text.endswith('```'):
    #                 response_text = response_text[:-3]
                
    #             response_text = response_text.strip()
                
    #             # Parse the cleaned JSON response
    #             evaluation = json.loads(response_text)
                
    #             # Validate required fields
    #             required_fields = [
    #                 "impact_score", "worth_reading", "key_insights",
    #                 "originality_score", "evidence_quality", "target_audience",
    #                 "estimated_reading_time", "time_value_assessment",
    #                 "confidence_in_evaluation"
    #             ]
                
    #             for field in required_fields:
    #                 if field not in evaluation:
    #                     raise ValueError(f"Missing required field: {field}")
                
    #             return evaluation
                
    #         except Exception as e:
    #             print(f"Error in Gemini evaluation: {e}")
    #             print(f"Raw response: {response.text if 'response' in locals() else 'No response'}")
                
    #             # Return a default evaluation
    #             return {
    #                 "impact_score": 5,
    #                 "worth_reading": False,
    #                 "key_insights": ["Evaluation failed"],
    #                 "originality_score": 5,
    #                 "evidence_quality": 5,
    #                 "target_audience": "Unknown",
    #                 "estimated_reading_time": 5,
    #                 "time_value_assessment": "Could not evaluate",
    #                 "confidence_in_evaluation": 0
    #             }


    # def curate_articles(self, days_ago: int = 7) -> List[Dict]:
    #     """Main function to find and curate impactful articles from all sources."""
    #     # Gather articles from all sources
    #     all_articles = []
    #     all_articles.extend(self.rss_extractor.get_articles(days_ago))
    #     all_articles.extend(self.reddit_extractor.get_articles(days_ago))
    #     all_articles.extend(self.arxiv_extractor.get_articles(days_ago))
    #     all_articles.extend(self.hn_extractor.get_articles(days_ago))
        
    #     # Remove duplicates based on URL
    #     seen_urls = set()
    #     unique_articles = []
    #     for article in all_articles:
    #         if article["url"] not in seen_urls:
    #             seen_urls.add(article["url"])
    #             unique_articles.append(article)
        
    #     curated_articles = []
    #     for article in unique_articles:
    #         # Extract content
    #         content = self.extract_article_content(
    #             article["url"], 
    #             source=article.get("source"),
    #             article_data=article
    #         )
            
    #         if not content:
    #             continue
                
    #         # For non-arXiv articles, check minimum length
    #         if article.get("source") != "arXiv" and len(content.split()) < 800:
    #             continue
                
    #         # Evaluate article
    #         evaluation = self.evaluate_article(
    #             article["title"], 
    #             content, 
    #             article["source"],
    #             article.get("is_paywalled", False)
    #         )
    #         if not evaluation:
    #             continue
                
    #         # Filter based on impact and originality
    #         if (evaluation.get("impact_score", 0) >= 7 and 
    #             evaluation.get("originality_score", 0) >= 6 and 
    #             evaluation.get("worth_reading", False)):
    #             curated_articles.append({
    #                 "title": article["title"],
    #                 "url": article["url"],
    #                 "source": article["source"],
    #                 "evaluation": evaluation
    #             })
        
    #     # Sort by combined score of impact and originality
    #     curated_articles.sort(
    #         key=lambda x: (
    #             x["evaluation"]["impact_score"] + 
    #             x["evaluation"]["originality_score"]
    #         ), 
    #         reverse=True
    #     )
    #     return curated_articles


# Added code for batch evaluation of articles
    def batch_evaluate_articles(self, articles_data: List[Dict], batch_size: int = 5) -> List[Dict]:
            """Evaluate multiple articles in a single Gemini call."""
            # Add sleep before API call
            time.sleep(2)  # Sleep for 2 seconds between batches
            
            prompt = f"""You are an expert article curator. Evaluate the following {batch_size} articles and provide a structured analysis for each.

    For each article, evaluate based on:
    1. Intellectual depth and rigor
    2. Novelty of insights
    3. Potential long-term significance
    4. Quality of argumentation
    5. Practical implications
    6. Citation of sources and evidence
    7. Unique perspective or analysis

    Provide your response as a JSON array of evaluations, with each evaluation following this exact structure:
    {{
        "impact_score": (1-10),
        "worth_reading": (boolean),
        "key_insights": ["insight1", "insight2", "insight3"],
        "originality_score": (1-10),
        "evidence_quality": (1-10),
        "target_audience": "description",
        "estimated_reading_time": (minutes),
        "time_value_assessment": "explanation",
        "confidence_in_evaluation": (1-10)
    }}

    Here are the articles:

    {articles_data}

    Return ONLY a JSON array containing evaluations, nothing else before or after."""

            try:
                # Add retry mechanism with exponential backoff
                max_retries = 3
                retry_delay = 5  # Starting delay in seconds
                
                for attempt in range(max_retries):
                    try:
                        response = self.model.generate_content(
                            prompt,
                            generation_config=genai.types.GenerationConfig(
                                temperature=0.1,
                                top_p=0.8,
                                top_k=40
                            )
                        )
                        break  # If successful, break the retry loop
                    except Exception as e:
                        if attempt == max_retries - 1:  # Last attempt
                            raise e
                        print(f"Attempt {attempt + 1} failed. Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                
                # Clean and parse response
                response_text = response.text.strip()
                if response_text.startswith('```json'):
                    response_text = response_text[7:]
                if response_text.endswith('```'):
                    response_text = response_text[:-3]
                
                evaluations = json.loads(response_text)
                if not isinstance(evaluations, list):
                    evaluations = [evaluations]
                
                return evaluations
                
            except Exception as e:
                print(f"Error in batch Gemini evaluation: {e}")
                print(f"Raw response: {response.text if 'response' in locals() else 'No response'}")
                return [self.get_default_evaluation() for _ in range(len(articles_data))]

    def curate_articles(self, days_ago: int = 7) -> List[Dict]:
        """Main function to find and curate impactful articles from all sources."""
        print("Starting article curation...")
        
        # Gather articles from all sources with delays
        all_articles = []
        
        print("Fetching RSS articles...")
        time.sleep(1)
        all_articles.extend(self.rss_extractor.get_articles(days_ago))
        
        print("Fetching Reddit articles...")
        time.sleep(1)
        all_articles.extend(self.reddit_extractor.get_articles(days_ago))
        
        print("Fetching arXiv articles...")
        time.sleep(1)
        all_articles.extend(self.arxiv_extractor.get_articles(days_ago))
        
        print("Fetching HackerNews articles...")
        time.sleep(1)
        all_articles.extend(self.hn_extractor.get_articles(days_ago))
        
        print(f"Total articles gathered: {len(all_articles)}")
        
        # Remove duplicates based on URL
        seen_urls = set()
        unique_articles = []
        for article in all_articles:
            if article["url"] not in seen_urls:
                seen_urls.add(article["url"])
                unique_articles.append(article)
        
        print(f"Unique articles after deduplication: {len(unique_articles)}")
        
        # Process articles in batches
        batch_size = 3  # Reduced batch size for better reliability
        curated_articles = []
        current_batch = []
        batch_data = []
        
        for idx, article in enumerate(unique_articles):
            print(f"Processing article {idx + 1}/{len(unique_articles)}")
            
            # Add small delay between content extractions
            time.sleep(0.5)
            
            # Extract content
            content = self.extract_article_content(
                article["url"], 
                source=article.get("source"),
                article_data=article
            )
            
            if not content:
                continue
                
            # For non-arXiv articles, check minimum length
            if article.get("source") != "arXiv" and len(content.split()) < 800:
                continue
            
            # Prepare article data for batch evaluation
            article_data = {
                "title": article["title"],
                "content": content[:3000],  # Reduced content length for reliability
                "source": article["source"],
                "is_paywalled": article.get("is_paywalled", False)
            }
            
            current_batch.append(article)
            batch_data.append(article_data)
            
            # Process batch when it reaches batch_size
            if len(current_batch) == batch_size:
                print(f"Evaluating batch of {batch_size} articles...")
                evaluations = self.batch_evaluate_articles(batch_data, batch_size)
                
                # Add evaluated articles to curated list
                for idx, (eval_result, orig_article) in enumerate(zip(evaluations, current_batch)):
                    if (eval_result.get("impact_score", 0) >= 7 and 
                        eval_result.get("originality_score", 0) >= 6 and 
                        eval_result.get("worth_reading", False)):
                        curated_articles.append({
                            "title": orig_article["title"],
                            "url": orig_article["url"],
                            "source": orig_article["source"],
                            "evaluation": eval_result
                        })
                
                # Reset batch
                current_batch = []
                batch_data = []
                time.sleep(3)  # Additional sleep between batches
        
        # Process remaining articles
        if current_batch:
            print(f"Evaluating final batch of {len(current_batch)} articles...")
            evaluations = self.batch_evaluate_articles(batch_data, len(current_batch))
            for idx, (eval_result, orig_article) in enumerate(zip(evaluations, current_batch)):
                if (eval_result.get("impact_score", 0) >= 7 and 
                    eval_result.get("originality_score", 0) >= 6 and 
                    eval_result.get("worth_reading", False)):
                    curated_articles.append({
                        "title": orig_article["title"],
                        "url": orig_article["url"],
                        "source": orig_article["source"],
                        "evaluation": eval_result
                    })
        
        print(f"Final curated articles count: {len(curated_articles)}")
        
        # Sort by combined score
        curated_articles.sort(
            key=lambda x: (
                x["evaluation"]["impact_score"] + 
                x["evaluation"]["originality_score"]
            ), 
            reverse=True
        )
        
        return curated_articles