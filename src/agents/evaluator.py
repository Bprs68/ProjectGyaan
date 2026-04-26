import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

EVAL_MODEL = os.environ.get("EVAL_MODEL", "anthropic/claude-sonnet-4-6")


class ArticleEvaluator:
    def __init__(self):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
            default_headers={"X-Title": "Project Gyaan"},
        )

    def evaluate_batch(
        self, articles: List[Dict[str, Any]], batch_size: int = 3, max_workers: int = 4
    ) -> List[Dict[str, Any]]:
        """Evaluate articles in parallel batches. Results maintain input order."""
        batches = [articles[i : i + batch_size] for i in range(0, len(articles), batch_size)]
        results: List[Optional[List]] = [None] * len(batches)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(self._evaluate_single_batch, batch): idx
                for idx, batch in enumerate(batches)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.error(f"Batch {idx} evaluation failed: {e}")
                    results[idx] = [self._default_evaluation() for _ in batches[idx]]

        all_evaluations: List[Dict[str, Any]] = []
        for batch_result in results:
            all_evaluations.extend(batch_result or [])
        return all_evaluations

    def _evaluate_single_batch(
        self, articles: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        articles_text = ""
        for idx, a in enumerate(articles, 1):
            content = a.get("content", a.get("snippet", ""))[:3000]
            articles_text += (
                f"\nArticle {idx}:\n"
                f"Title: {a['title']}\n"
                f"Source: {a.get('source', 'Unknown')}\n"
                f"Topic: {a.get('topic_name', 'Unknown')}\n"
                f"Content: {content}\n"
            )

        prompt = f"""You are an expert editorial curator. Evaluate the following {len(articles)} articles strictly for depth, research quality, and intellectual value. Reject shallow news summaries.

Scoring criteria (1-10):
- impact_score: real-world significance, why this matters
- originality_score: novel angle, non-obvious insights
- depth_score: research rigour, evidence, detail (most important)

Article types:
- DEEP: long-form analysis, high intellectual depth, >15 min read
- FEATURE: investigative journalism, narrative non-fiction
- ANALYSIS: data-backed expert commentary
- RESEARCH: academic / technical deep dive
- BRIEF: concise but high-value synthesis

{articles_text}

Return ONLY a JSON array with exactly {len(articles)} objects in the same order:
[
  {{
    "impact_score": 8,
    "originality_score": 7,
    "depth_score": 9,
    "worth_reading": true,
    "key_insights": ["First key insight", "Second key insight", "Third key insight"],
    "reading_time_mins": 20,
    "article_type": "DEEP",
    "summary": "Two-sentence summary of the article and why it matters intellectually."
  }}
]

Set worth_reading to false and all scores below 5 for anything that is a shallow news brief, listicle, or marketing content.
The summary must describe the article's actual content and why it matters — never comment on content length, truncation, or how much text you received."""

        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=EVAL_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                )
                text = response.choices[0].message.content.strip()
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]

                evaluations = json.loads(text.strip())
                if not isinstance(evaluations, list):
                    evaluations = [evaluations]

                while len(evaluations) < len(articles):
                    evaluations.append(self._default_evaluation())

                for ev in evaluations:
                    ev["combined_score"] = round(
                        ev.get("impact_score", 0) * 0.4
                        + ev.get("originality_score", 0) * 0.3
                        + ev.get("depth_score", 0) * 0.3,
                        2,
                    )
                    ev["score_pct"] = int(round(ev["combined_score"] * 10))

                return evaluations[: len(articles)]

            except Exception as e:
                logger.error(f"Evaluation attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))

        return [self._default_evaluation() for _ in articles]

    @staticmethod
    def _default_evaluation() -> Dict[str, Any]:
        return {
            "impact_score": 0,
            "originality_score": 0,
            "depth_score": 0,
            "combined_score": 0,
            "score_pct": 0,
            "worth_reading": False,
            "key_insights": [],
            "reading_time_mins": 5,
            "article_type": "ANALYSIS",
            "summary": "Evaluation unavailable.",
        }
