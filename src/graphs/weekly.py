import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

from langgraph.graph import END, StateGraph
from openai import OpenAI
from typing_extensions import TypedDict

from src.db.database import SessionLocal
from src.db.models import Article, Digest, Evaluation, Feedback, PipelineRun, Topic
from src.email_digest import EmailDigest

logger = logging.getLogger(__name__)

SUMMARY_MODEL = os.environ.get("EVAL_MODEL", "anthropic/claude-sonnet-4-6")


class WeeklyState(TypedDict):
    run_id: int
    week_start: str
    week_end: str
    candidate_articles: List[Dict[str, Any]]
    selected_articles: List[Dict[str, Any]]
    week_summary: str
    email_sent: bool
    errors: List[str]


# ── nodes ──────────────────────────────────────────────────────────────────

def load_week_articles(state: WeeklyState) -> WeeklyState:
    db = SessionLocal()
    errors = list(state.get("errors", []))
    try:
        week_start = datetime.fromisoformat(state["week_start"])
        week_end = datetime.fromisoformat(state["week_end"])

        articles = (
            db.query(Article)
            .join(Evaluation)
            .filter(
                Article.collected_at >= week_start,
                Article.collected_at <= week_end,
                Article.status == "evaluated",
                Evaluation.worth_reading == True,
                Evaluation.impact_score >= 6,
                Evaluation.depth_score >= 5,
            )
            .all()
        )

        # Feedback multipliers per topic (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        topic_feedback: Dict[int, tuple] = {}
        for topic in db.query(Topic).all():
            article_ids = [
                a.id
                for a in db.query(Article)
                .filter(Article.topic_id == topic.id)
                .all()
            ]
            if not article_ids:
                topic_feedback[topic.id] = (1.0, topic.weight)
                continue
            liked = (
                db.query(Feedback)
                .filter(
                    Feedback.article_id.in_(article_ids),
                    Feedback.rating == "liked",
                    Feedback.created_at >= thirty_days_ago,
                )
                .count()
            )
            disliked = (
                db.query(Feedback)
                .filter(
                    Feedback.article_id.in_(article_ids),
                    Feedback.rating == "disliked",
                    Feedback.created_at >= thirty_days_ago,
                )
                .count()
            )
            multiplier = max(
                0.5,
                min(2.0, 1.0 + 0.5 * (liked - disliked) / (liked + disliked + 1)),
            )
            topic_feedback[topic.id] = (multiplier, topic.weight)

        candidates: List[Dict[str, Any]] = []
        for article in articles:
            ev = article.evaluation
            fb_mult, t_weight = topic_feedback.get(article.topic_id, (1.0, 1.0))
            adjusted = ev.combined_score * t_weight * fb_mult

            candidates.append(
                {
                    "id": article.id,
                    "title": article.title,
                    "url": article.url,
                    "source": article.source or "",
                    "topic_name": article.topic.name if article.topic else "General",
                    "impact_score": ev.impact_score,
                    "originality_score": ev.originality_score,
                    "depth_score": ev.depth_score,
                    "score_pct": ev.score_pct,
                    "key_insights": ev.key_insights or [],
                    "reading_time_mins": ev.reading_time_mins,
                    "article_type": ev.article_type,
                    "summary": ev.summary or "",
                    "adjusted_score": adjusted,
                }
            )

        candidates.sort(key=lambda x: x["adjusted_score"], reverse=True)
        logger.info(f"Found {len(candidates)} candidate articles")
        return {**state, "candidate_articles": candidates, "errors": errors}
    finally:
        db.close()


def select_top_articles(state: WeeklyState) -> WeeklyState:
    """Pick top 15 with max 3 per topic for variety."""
    selected: List[Dict[str, Any]] = []
    topic_counts: Dict[str, int] = {}

    for article in state["candidate_articles"]:
        topic = article["topic_name"]
        if topic_counts.get(topic, 0) < 3:
            selected.append(article)
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        if len(selected) >= 15:
            break

    logger.info(f"Selected {len(selected)} articles for digest")
    return {**state, "selected_articles": selected}


def generate_summary(state: WeeklyState) -> WeeklyState:
    """Write a narrative Week in Review using the selected articles."""
    articles = state["selected_articles"]
    errors = list(state.get("errors", []))

    if not articles:
        return {**state, "week_summary": "", "errors": errors}

    # Build a compact article list for the prompt
    article_lines = "\n".join(
        f"- [{a['topic_name']}] {a['title']} | {a['source']} — {a.get('summary', '')}"
        for a in articles
    )

    prompt = f"""You are writing a 3-sentence "week in review" that goes at the top of a personal reading digest.

Rules:
- Exactly 3 sentences. No more.
- Casual, direct, a little dry — like a smart friend texting you what's actually worth caring about this week.
- Pick the 2-3 most interesting/surprising things from the list. Ignore the rest.
- No grand conclusions, no "this week asked us to consider..." framing. Just say the thing.
- If something is genuinely weird or funny, lean into it.

Articles this week:
{article_lines}

Write the 3 sentences now:"""

    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
            default_headers={"X-Title": "Project Gyaan"},
        )
        response = client.chat.completions.create(
            model=SUMMARY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
        )
        summary = response.choices[0].message.content.strip()
    except Exception as e:
        errors.append(f"Summary generation failed: {e}")
        logger.error(f"Weekly summary error: {e}")
        summary = ""

    logger.info("Generated week-in-review summary")
    return {**state, "week_summary": summary, "errors": errors}


def send_digest(state: WeeklyState) -> WeeklyState:
    errors = list(state.get("errors", []))
    articles = state["selected_articles"]
    week_summary = state.get("week_summary", "")

    try:
        email_config = {
            "server": "smtp.gmail.com",
            "port": 465,
            "username": os.environ["SMTP_USERNAME"],
            "password": os.environ["SMTP_PASSWORD"],
        }
        emailer = EmailDigest(email_config)
        success = emailer.send_digest(
            articles,
            to_email=os.environ["RECIPIENT_EMAIL"],
            week_summary=week_summary,
        )

        if success:
            db = SessionLocal()
            try:
                digest = Digest(
                    week_start=datetime.fromisoformat(state["week_start"]),
                    week_end=datetime.fromisoformat(state["week_end"]),
                    sent_at=datetime.utcnow(),
                    article_ids=[a["id"] for a in articles],
                    summary=week_summary or None,
                )
                db.add(digest)
                for a in articles:
                    article = db.get(Article, a["id"])
                    if article:
                        article.status = "digest"
                run = db.get(PipelineRun, state["run_id"])
                if run:
                    run.status = "success"
                    run.completed_at = datetime.utcnow()
                    run.articles_stored = len(articles)
                db.commit()
            finally:
                db.close()

        return {**state, "email_sent": success, "errors": errors}

    except Exception as e:
        errors.append(f"Email send failed: {e}")
        logger.error(f"Weekly digest failed: {e}")
        return {**state, "email_sent": False, "errors": errors}


# ── graph ──────────────────────────────────────────────────────────────────

def _build_graph():
    g = StateGraph(WeeklyState)
    g.add_node("load_articles", load_week_articles)
    g.add_node("select_top", select_top_articles)
    g.add_node("generate_summary", generate_summary)
    g.add_node("send", send_digest)

    g.set_entry_point("load_articles")
    g.add_edge("load_articles", "select_top")
    g.add_edge("select_top", "generate_summary")
    g.add_edge("generate_summary", "send")
    g.add_edge("send", END)

    return g.compile()


def run_weekly_digest() -> Dict[str, Any]:
    now = datetime.utcnow()
    week_start = now - timedelta(days=7)

    db = SessionLocal()
    try:
        run = PipelineRun(run_type="weekly", status="running")
        db.add(run)
        db.commit()
        run_id = run.id
    finally:
        db.close()

    graph = _build_graph()
    initial: WeeklyState = {
        "run_id": run_id,
        "week_start": week_start.isoformat(),
        "week_end": now.isoformat(),
        "candidate_articles": [],
        "selected_articles": [],
        "week_summary": "",
        "email_sent": False,
        "errors": [],
    }

    logger.info("Starting weekly digest pipeline")
    result = graph.invoke(initial)
    logger.info(f"Weekly digest complete — email_sent: {result['email_sent']}")
    return result
