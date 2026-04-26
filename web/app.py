import os
import threading
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
load_dotenv()  # must run before LangGraph/LangChain imports so LangSmith env vars are picked up

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.db.database import get_db, init_db
from src.db.models import Article, Digest, Evaluation, Feedback, PipelineRun, Topic

app = FastAPI(title="Project Gyaan")
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")


@app.on_event("startup")
async def startup():
    init_db()


# ── helpers ────────────────────────────────────────────────────────────────

def _get_stats(db: Session) -> dict:
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    articles_this_week = db.query(Article).filter(Article.collected_at >= week_ago).count()
    digest_count = (
        db.query(Article)
        .join(Evaluation)
        .filter(
            Article.collected_at >= week_ago,
            Article.status.in_(["evaluated", "digest"]),
            Evaluation.worth_reading == True,
        )
        .count()
    )
    liked = (
        db.query(Feedback)
        .filter(Feedback.created_at >= week_ago, Feedback.rating == "liked")
        .count()
    )
    disliked = (
        db.query(Feedback)
        .filter(Feedback.created_at >= week_ago, Feedback.rating == "disliked")
        .count()
    )

    days_until_sunday = (6 - now.weekday()) % 7 or 7
    next_sunday = now + timedelta(days=days_until_sunday)
    next_email = next_sunday.strftime("%a %b %d, 08:00")

    last_run = (
        db.query(PipelineRun)
        .filter(PipelineRun.status == "success")
        .order_by(desc(PipelineRun.completed_at))
        .first()
    )
    if last_run and last_run.completed_at:
        delta = now - last_run.completed_at
        if delta.days == 0:
            h, rem = divmod(delta.seconds, 3600)
            last_run_str = f"{h}h {rem//60}m ago" if h else f"{rem//60}m ago"
        else:
            last_run_str = last_run.completed_at.strftime("%b %d")
    else:
        last_run_str = "Never"

    running = (
        db.query(PipelineRun)
        .filter(PipelineRun.status == "running")
        .order_by(desc(PipelineRun.started_at))
        .first()
    )

    return {
        "articles_this_week": articles_this_week,
        "digest_count": digest_count,
        "liked": liked,
        "disliked": disliked,
        "next_email": next_email,
        "last_run": last_run_str,
        "pipeline_running": running is not None,
    }


# ── pages ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/digest")


@app.get("/digest/preview", response_class=HTMLResponse)
async def digest_preview(db: Session = Depends(get_db)):
    """Render the weekly email HTML in the browser without sending it."""
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    articles = (
        db.query(Article)
        .join(Evaluation)
        .filter(
            Article.collected_at >= week_ago,
            Evaluation.worth_reading == True,
            Evaluation.impact_score >= 6,
        )
        .order_by(desc(Evaluation.combined_score))
        .limit(15)
        .all()
    )

    flat = [
        {
            "title": a.title,
            "url": a.url,
            "source": a.source or "",
            "topic_name": a.topic.name if a.topic else "General",
            "article_type": a.evaluation.article_type if a.evaluation else "ANALYSIS",
            "score_pct": a.evaluation.score_pct if a.evaluation else 0,
            "reading_time_mins": a.evaluation.reading_time_mins if a.evaluation else 0,
            "key_insights": a.evaluation.key_insights if a.evaluation else [],
            "summary": a.evaluation.summary if a.evaluation else "",
        }
        for a in articles
    ]

    from src.email_digest import EmailDigest
    html = EmailDigest({}).format_article_html(flat) if flat else EmailDigest({}).format_no_articles_html()
    return HTMLResponse(content=html)


@app.get("/digest", response_class=HTMLResponse)
async def digest_page(request: Request, db: Session = Depends(get_db)):
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    articles = (
        db.query(Article)
        .join(Evaluation)
        .filter(
            Article.collected_at >= week_ago,
            Evaluation.worth_reading == True,
            Evaluation.impact_score >= 6,
        )
        .order_by(desc(Evaluation.combined_score))
        .limit(15)
        .all()
    )

    feedback_map = {}
    for a in articles:
        fb = (
            db.query(Feedback)
            .filter(Feedback.article_id == a.id)
            .order_by(desc(Feedback.created_at))
            .first()
        )
        if fb:
            feedback_map[a.id] = {"rating": fb.rating, "note": fb.note or ""}

    stats = _get_stats(db)
    week_label = f"{week_ago.strftime('%b %d')} – {now.strftime('%b %d, %Y')}"

    # Show summary from the most recent sent digest if it covers this week
    latest_digest = (
        db.query(Digest)
        .filter(Digest.sent_at >= week_ago)
        .order_by(desc(Digest.sent_at))
        .first()
    )
    week_summary = latest_digest.summary if latest_digest and latest_digest.summary else ""

    return templates.TemplateResponse(
        request,
        "digest.html",
        {
            "articles": articles,
            "feedback_map": feedback_map,
            "stats": stats,
            "week_label": week_label,
            "week_summary": week_summary,
            "active": "digest",
        },
    )


@app.get("/topics", response_class=HTMLResponse)
async def topics_page(request: Request, db: Session = Depends(get_db)):
    topics = db.query(Topic).order_by(Topic.name).all()
    topic_counts = {
        t.id: db.query(Article).filter(Article.topic_id == t.id).count()
        for t in topics
    }
    stats = _get_stats(db)
    return templates.TemplateResponse(
        request,
        "topics.html",
        {
            "topics": topics,
            "topic_counts": topic_counts,
            "stats": stats,
            "active": "topics",
        },
    )


@app.get("/library", response_class=HTMLResponse)
async def library_page(
    request: Request,
    topic: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    db: Session = Depends(get_db),
):
    query = db.query(Article).join(Evaluation, isouter=True).join(Topic, isouter=True)
    if topic:
        query = query.filter(Topic.name == topic)
    if status:
        query = query.filter(Article.status == status)
    if search:
        query = query.filter(Article.title.ilike(f"%{search}%"))

    total = query.count()
    page_size = 20
    articles = (
        query.order_by(desc(Article.collected_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    topics = db.query(Topic).order_by(Topic.name).all()
    stats = _get_stats(db)

    return templates.TemplateResponse(
        request,
        "library.html",
        {
            "articles": articles,
            "topics": topics,
            "stats": stats,
            "selected_topic": topic,
            "selected_status": status,
            "search": search or "",
            "page": page,
            "total": total,
            "pages": max(1, (total + page_size - 1) // page_size),
            "active": "library",
        },
    )


@app.get("/pipeline", response_class=HTMLResponse)
async def pipeline_page(request: Request, db: Session = Depends(get_db)):
    runs = (
        db.query(PipelineRun)
        .order_by(desc(PipelineRun.started_at))
        .limit(20)
        .all()
    )
    stats = _get_stats(db)
    return templates.TemplateResponse(
        request,
        "pipeline.html",
        {
            "runs": runs,
            "stats": stats,
            "active": "pipeline",
        },
    )


@app.get("/schema", response_class=HTMLResponse)
async def schema_page(request: Request, db: Session = Depends(get_db)):
    counts = {
        "topics": db.query(Topic).count(),
        "articles": db.query(Article).count(),
        "evaluations": db.query(Evaluation).count(),
        "feedback": db.query(Feedback).count(),
        "digests": db.query(Digest).count(),
        "pipeline_runs": db.query(PipelineRun).count(),
    }
    stats = _get_stats(db)
    return templates.TemplateResponse(
        request,
        "schema.html",
        {
            "counts": counts,
            "stats": stats,
            "active": "schema",
        },
    )


# ── API endpoints ──────────────────────────────────────────────────────────

@app.post("/api/feedback")
async def submit_feedback(
    article_id: int = Form(...),
    rating: str = Form(...),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    if rating not in ("liked", "disliked", "neutral"):
        raise HTTPException(status_code=400, detail="Invalid rating")
    if not db.get(Article, article_id):
        raise HTTPException(status_code=404, detail="Article not found")

    db.query(Feedback).filter(Feedback.article_id == article_id).delete()
    db.add(Feedback(article_id=article_id, rating=rating, note=note.strip() or None))
    db.commit()
    return JSONResponse({"status": "ok", "rating": rating})


@app.post("/api/topics/{topic_id}")
async def update_topic(
    topic_id: int,
    name: Optional[str] = Form(None),
    weight: Optional[float] = Form(None),
    active: Optional[bool] = Form(None),
    search_queries: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    topic = db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    if name is not None:
        topic.name = name
    if weight is not None:
        topic.weight = max(0.1, min(3.0, weight))
    if active is not None:
        topic.active = active
    if search_queries is not None:
        topic.search_queries = [q.strip() for q in search_queries.splitlines() if q.strip()]
    db.commit()
    return JSONResponse({"status": "ok"})


@app.post("/api/pipeline/run")
async def trigger_pipeline(run_type: str = Form("daily")):
    def _run():
        if run_type == "daily":
            from src.graphs.daily import run_daily_pipeline
            run_daily_pipeline()
        elif run_type == "weekly":
            from src.graphs.weekly import run_weekly_digest
            run_weekly_digest()

    threading.Thread(target=_run, daemon=True).start()
    return JSONResponse({"status": "started", "run_type": run_type})


@app.get("/api/pipeline/status")
async def pipeline_status(db: Session = Depends(get_db)):
    run = (
        db.query(PipelineRun)
        .order_by(desc(PipelineRun.started_at))
        .first()
    )
    if not run:
        return JSONResponse({"status": "idle"})
    return JSONResponse(
        {
            "id": run.id,
            "run_type": run.run_type,
            "status": run.status,
            "articles_found": run.articles_found,
            "articles_evaluated": run.articles_evaluated,
            "articles_stored": run.articles_stored,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }
    )
