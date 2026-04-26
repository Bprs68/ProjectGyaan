import argparse
import logging
import os
import sys
import threading
import time

from dotenv import load_dotenv

load_dotenv()


def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("gyaan.log"),
            logging.StreamHandler(),
        ],
    )


def _start_web(host: str, port: int):
    import uvicorn
    uvicorn.run("web.app:app", host=host, port=port, reload=False, log_level="warning")


def _run_daily():
    from src.graphs.daily import run_daily_pipeline
    run_daily_pipeline()


def _run_weekly():
    from src.graphs.weekly import run_weekly_digest
    run_weekly_digest()


def main():
    parser = argparse.ArgumentParser(description="Project Gyaan — Intelligence Digest")
    parser.add_argument("--web",    action="store_true", help="Web server only")
    parser.add_argument("--daily",  action="store_true", help="Run daily pipeline once and exit")
    parser.add_argument("--weekly", action="store_true", help="Run weekly digest once and exit")
    parser.add_argument("--host",   default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port",   type=int, default=int(os.environ.get("PORT", 8000)))
    args = parser.parse_args()

    _setup_logging()
    logger = logging.getLogger(__name__)

    # Always initialise DB
    from src.db.database import init_db
    init_db()

    if args.daily:
        logger.info("Running daily pipeline…")
        _run_daily()
        return

    if args.weekly:
        logger.info("Running weekly digest…")
        _run_weekly()
        return

    if args.web:
        logger.info(f"Starting web server on http://{args.host}:{args.port}")
        _start_web(args.host, args.port)
        return

    # Default: scheduler + web server together
    import schedule

    schedule.every().day.at("08:00").do(_run_daily)
    schedule.every().sunday.at("20:00").do(_run_weekly)

    web_thread = threading.Thread(
        target=_start_web, args=(args.host, args.port), daemon=True
    )
    web_thread.start()

    print(f"\n  Project Gyaan running → http://{args.host}:{args.port}")
    print("  Daily pipeline   : 08:00 every day")
    print("  Weekly digest    : Sunday 20:00")
    print("  Press Ctrl+C to stop\n")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        print("\nShutting down…")


if __name__ == "__main__":
    main()
