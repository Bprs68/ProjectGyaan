import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from src.db.models import Base, Topic

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///gyaan.db")

_connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, echo=False)

if DATABASE_URL.startswith("sqlite"):
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.commit()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate()
    _seed_topics()


def _migrate():
    """Apply incremental schema changes to existing databases."""
    migrations = [
        "ALTER TABLE digests ADD COLUMN summary TEXT",
        "ALTER TABLE topics ADD COLUMN rss_feeds JSON",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # column already exists


def _seed_topics():
    db = SessionLocal()
    try:
        if db.query(Topic).count() > 0:
            return
        topics = [
            Topic(
                name="Geopolitics",
                weight=1.0,
                description="International relations, foreign policy, and global power dynamics",
                search_queries=[
                    "geopolitics explained analysis 2025 foreignaffairs.com",
                    "international relations deep dive foreignpolicy.com OR economist.com",
                    "foreign policy longread explainer theguardian.com OR theatlantic.com",
                    "global power shifts alliances news analysis 2025",
                ],
                rss_feeds=[
                    "https://foreignpolicy.com/feed/",
                    "https://warontherocks.com/feed/",
                    "https://www.bellingcat.com/feed/",
                    "https://www.cfr.org/node/feed",
                ],
            ),
            Topic(
                name="Artificial Intelligence",
                weight=1.0,
                description="AI research, policy, ethics, and technology analysis",
                search_queries=[
                    "AI breakthrough explained 2025 wired.com OR technologyreview.com",
                    "large language models future implications analysis",
                    "AI policy regulation societal impact longread",
                    "artificial intelligence real-world consequences analysis 2025",
                ],
                rss_feeds=[
                    "https://www.technologyreview.com/feed/",
                    "https://thegradient.pub/rss/",
                    "https://importai.substack.com/feed",
                    "https://www.wired.com/feed/tag/artificial-intelligence/rss",
                ],
            ),
            Topic(
                name="History",
                weight=0.8,
                description="Historical analysis and context for modern events",
                search_queries=[
                    "history longread modern parallels theatlantic.com OR newyorker.com",
                    "historical context current events analysis 2025",
                    "forgotten history perspective feature journalism",
                ],
                rss_feeds=[
                    "https://daily.jstor.org/feed/",
                    "https://www.historytoday.com/feed",
                    "https://www.smithsonianmag.com/rss/latest_articles/",
                ],
            ),
            Topic(
                name="The Guardian",
                weight=1.2,
                description="The Guardian — long reads, investigations, and features",
                search_queries=[
                    "the guardian long read investigation 2025",
                    "the guardian feature analysis society culture 2025",
                    "the guardian explainer in-depth reporting 2025",
                ],
                rss_feeds=[
                    "https://www.theguardian.com/news/series/long-reads/rss",
                    "https://www.theguardian.com/world/rss",
                    "https://www.theguardian.com/technology/rss",
                ],
            ),
            Topic(
                name="Long Reads",
                weight=1.1,
                description="Long-form journalism and narrative non-fiction from across the web",
                search_queries=[
                    "longform investigative feature journalism 2025 newyorker.com OR theatlantic.com",
                    "narrative non-fiction in-depth feature 2025",
                    "longread essay culture society 2025",
                ],
                rss_feeds=[
                    "https://longreads.com/feed/",
                    "https://www.theatlantic.com/feed/all/",
                    "https://www.newyorker.com/feed/everything",
                    "https://www.vox.com/rss/index.xml",
                ],
            ),
            Topic(
                name="Science & Research",
                weight=0.9,
                description="Scientific research, discoveries, and their implications",
                search_queries=[
                    "science discovery implications explained 2025 quantamagazine.org",
                    "new research findings real world impact analysis technologyreview.com",
                    "scientific breakthrough what it means longread 2025",
                ],
                rss_feeds=[
                    "https://www.quantamagazine.org/feed/",
                    "https://feeds.arstechnica.com/arstechnica/science",
                    "https://www.newscientist.com/feed/home/",
                ],
            ),
            Topic(
                name="Economics & Finance",
                weight=0.9,
                description="Economic analysis, policy, and financial systems",
                search_queries=[
                    "economics analysis policy 2025 economist.com OR ft.com",
                    "macroeconomics explained longread theatlantic.com OR vox.com",
                    "economic trends consequences analysis 2025",
                ],
                rss_feeds=[
                    "https://noahpinion.substack.com/feed",
                    "https://www.economist.com/finance-and-economics/rss.xml",
                    "https://marginalrevolution.com/feed",
                    "https://feeds.feedburner.com/typepad/krugman",
                ],
            ),
        ]
        db.add_all(topics)
        db.commit()
    finally:
        db.close()
