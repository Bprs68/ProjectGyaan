import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from src.agents.discovery import DiscoveryAgent, _is_non_article_url
from src.agents.evaluator import ArticleEvaluator
from src.agents.extractor import ContentExtractor
from src.agents.rss_agent import RSSAgent
from src.db.database import SessionLocal
from src.db.models import Article, Evaluation, PipelineRun, Topic

logger = logging.getLogger(__name__)

EVAL_MODEL = "anthropic/claude-sonnet-4-6"


class DailyState(TypedDict):
    run_id: int
    topics: List[Dict[str, Any]]
    search_results: List[Dict[str, Any]]
    articles_to_evaluate: List[Dict[str, Any]]
    evaluated_articles: List[Dict[str, Any]]
    stored_count: int
    errors: List[str]


# ── nodes ──────────────────────────────────────────────────────────────────

def load_topics(state: DailyState) -> DailyState:
    db = SessionLocal()
    try:
        topics = db.query(Topic).filter(Topic.active == True).all()
        return {
            **state,
            "topics": [
                {
                    "id": t.id,
                    "name": t.name,
                    "weight": t.weight,
                    "queries": t.search_queries or [],
                    "rss_feeds": t.rss_feeds or [],
                }
                for t in topics
            ],
        }
    finally:
        db.close()


def discover_articles(state: DailyState) -> DailyState:
    discovery = DiscoveryAgent()
    errors = list(state.get("errors", []))

    db = SessionLocal()
    existing_urls = {url for (url,) in db.query(Article.url).all()}
    db.close()

    all_results: List[Dict[str, Any]] = []

    def _search_topic(topic: Dict[str, Any]):
        results = discovery.search_topic(
            topic_name=topic["name"],
            queries=topic["queries"],
            max_per_query=5,
        )
        new = [
            r for r in results
            if r["url"] not in existing_urls and not _is_non_article_url(r["url"])
        ]
        for r in new:
            r["topic_id"] = topic["id"]
        return new[:15]

    # Run topic searches in parallel (2 at a time to respect Tavily rate limits)
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_topic = {
            executor.submit(_search_topic, topic): topic
            for topic in state["topics"]
        }
        for future in as_completed(future_to_topic):
            topic = future_to_topic[future]
            try:
                all_results.extend(future.result())
            except Exception as e:
                errors.append(f"Discovery failed for {topic['name']}: {e}")
                logger.error(f"Discovery error for {topic['name']}: {e}")

    # HN front-page scan across all topics in one shot
    try:
        frontpage = discovery.get_hn_frontpage(state["topics"])
        for r in frontpage:
            if r["url"] not in existing_urls and r["url"] not in {x["url"] for x in all_results}:
                all_results.append(r)
    except Exception as e:
        errors.append(f"HN front page failed: {e}")
        logger.error(f"HN front page error: {e}")

    db = SessionLocal()
    run = db.get(PipelineRun, state["run_id"])
    if run:
        run.articles_found = len(all_results)
        db.commit()
    db.close()

    logger.info(f"Discovered {len(all_results)} new articles")
    return {**state, "search_results": all_results, "errors": errors}


def fetch_rss(state: DailyState) -> DailyState:
    agent = RSSAgent()
    errors = list(state.get("errors", []))
    existing_urls = {r["url"] for r in state["search_results"]}

    db = SessionLocal()
    db_urls = {url for (url,) in db.query(Article.url).all()}
    db.close()
    existing_urls |= db_urls

    new_results: List[Dict[str, Any]] = []

    def _fetch_topic(topic: Dict[str, Any]):
        feeds = topic.get("rss_feeds", [])
        if not feeds:
            return []
        results = agent.fetch_topic(
            topic_id=topic["id"],
            topic_name=topic["name"],
            feed_urls=feeds,
            max_per_feed=5,
        )
        return [r for r in results if r["url"] not in existing_urls and not _is_non_article_url(r["url"])]

    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_topic = {
            executor.submit(_fetch_topic, topic): topic
            for topic in state["topics"]
        }
        for future in as_completed(future_to_topic):
            topic = future_to_topic[future]
            try:
                results = future.result()
                for r in results:
                    if r["url"] not in existing_urls:
                        existing_urls.add(r["url"])
                        new_results.append(r)
            except Exception as e:
                errors.append(f"RSS failed for {topic['name']}: {e}")
                logger.error(f"RSS error for {topic['name']}: {e}")

    combined = state["search_results"] + new_results
    logger.info(f"RSS fetch added {len(new_results)} articles (total: {len(combined)})")
    return {**state, "search_results": combined, "errors": errors}


def extract_content(state: DailyState) -> DailyState:
    extractor = ContentExtractor()
    errors = list(state.get("errors", []))

    filtered = [r for r in state["search_results"] if r.get("relevance_score", 0) > 0.5]
    urls = [r["url"] for r in filtered]

    if not urls:
        return {**state, "articles_to_evaluate": [], "errors": errors}

    extracted = extractor.extract_batch(urls)

    articles_to_evaluate: List[Dict[str, Any]] = []
    for result in filtered:
        url = result["url"]
        content = extracted.get(url, result.get("snippet", ""))
        if not content or len(content.split()) < 600:
            continue
        articles_to_evaluate.append({**result, "content": content})

    logger.info(f"Extracted content for {len(articles_to_evaluate)} articles")
    return {**state, "articles_to_evaluate": articles_to_evaluate, "errors": errors}


def evaluate_articles(state: DailyState) -> DailyState:
    evaluator = ArticleEvaluator()
    errors = list(state.get("errors", []))
    articles = state["articles_to_evaluate"]

    if not articles:
        return {**state, "evaluated_articles": [], "errors": errors}

    try:
        evaluations = evaluator.evaluate_batch(articles, batch_size=3)
    except Exception as e:
        errors.append(f"Evaluation failed: {e}")
        logger.error(f"Evaluation error: {e}")
        return {**state, "evaluated_articles": [], "errors": errors}

    evaluated = [
        {**article, "evaluation": ev}
        for article, ev in zip(articles, evaluations)
    ]

    db = SessionLocal()
    run = db.get(PipelineRun, state["run_id"])
    if run:
        run.articles_evaluated = len(evaluated)
        db.commit()
    db.close()

    logger.info(f"Evaluated {len(evaluated)} articles")
    return {**state, "evaluated_articles": evaluated, "errors": errors}


def store_results(state: DailyState) -> DailyState:
    db = SessionLocal()
    stored_count = 0
    errors = list(state.get("errors", []))

    try:
        for item in state["evaluated_articles"]:
            ev = item["evaluation"]

            if db.query(Article).filter(Article.url == item["url"]).first():
                continue

            impact = ev.get("impact_score", 0)
            depth = ev.get("depth_score", 0)
            worth = ev.get("worth_reading", False)
            status = "evaluated" if (worth and impact >= 6 and depth >= 5) else "skipped"

            article = Article(
                title=item["title"],
                url=item["url"],
                source=item.get("source", ""),
                topic_id=item.get("topic_id"),
                content_snippet=item.get("content", "")[:1000],
                status=status,
            )
            db.add(article)
            db.flush()

            evaluation = Evaluation(
                article_id=article.id,
                impact_score=impact,
                originality_score=ev.get("originality_score", 0),
                depth_score=depth,
                combined_score=ev.get("combined_score", 0),
                score_pct=ev.get("score_pct", 0),
                key_insights=ev.get("key_insights", []),
                reading_time_mins=ev.get("reading_time_mins", 5),
                worth_reading=worth,
                article_type=ev.get("article_type", "ANALYSIS"),
                summary=ev.get("summary", ""),
                model_used=EVAL_MODEL,
            )
            db.add(evaluation)
            stored_count += 1

        db.commit()

        run = db.get(PipelineRun, state["run_id"])
        if run:
            run.articles_stored = stored_count
            run.status = "success"
            run.completed_at = datetime.utcnow()
            if errors:
                run.error_log = "\n".join(errors)
            db.commit()

    except Exception as e:
        db.rollback()
        errors.append(f"Storage failed: {e}")
        logger.error(f"Storage error: {e}")
        run = db.get(PipelineRun, state["run_id"])
        if run:
            run.status = "failed"
            run.completed_at = datetime.utcnow()
            run.error_log = "\n".join(errors)
            db.commit()
    finally:
        db.close()

    logger.info(f"Stored {stored_count} articles")
    return {**state, "stored_count": stored_count, "errors": errors}


# ── graph ──────────────────────────────────────────────────────────────────

def _build_graph():
    g = StateGraph(DailyState)
    g.add_node("load_topics", load_topics)
    g.add_node("discover", discover_articles)
    g.add_node("fetch_rss", fetch_rss)
    g.add_node("extract", extract_content)
    g.add_node("evaluate", evaluate_articles)
    g.add_node("store", store_results)

    g.set_entry_point("load_topics")
    g.add_edge("load_topics", "discover")
    g.add_edge("discover", "fetch_rss")
    g.add_edge("fetch_rss", "extract")
    g.add_edge("extract", "evaluate")
    g.add_edge("evaluate", "store")
    g.add_edge("store", END)

    return g.compile()


def run_daily_pipeline() -> Dict[str, Any]:
    db = SessionLocal()
    try:
        run = PipelineRun(run_type="daily", status="running")
        db.add(run)
        db.commit()
        run_id = run.id
    finally:
        db.close()

    graph = _build_graph()
    initial: DailyState = {
        "run_id": run_id,
        "topics": [],
        "search_results": [],
        "articles_to_evaluate": [],
        "evaluated_articles": [],
        "stored_count": 0,
        "errors": [],
    }

    logger.info(f"Starting daily pipeline (run_id={run_id})")
    result = graph.invoke(initial)
    logger.info(
        f"Daily pipeline complete — stored: {result['stored_count']}, "
        f"errors: {len(result['errors'])}"
    )
    return result
