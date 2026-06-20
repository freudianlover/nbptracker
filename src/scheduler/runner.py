"""
APScheduler-based long-running service.

Schedules:
    - Daily 12:30 UTC: fetch latest NBP rates via main.py
    - Hourly: evaluate alert rules

Run:
    python -m src.scheduler.runner
"""
import sys
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

import structlog
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.main import main as run_pipeline
from src.scheduler.check_alerts import AlertEvaluator
from src.loger import configure_logger


configure_logger()
log = structlog.get_logger()


def job_fetch_rates():
    """Wrapper: run pipeline + catch + log."""
    log.info("scheduled_job_started", job="fetch_rates")
    try:
        exit_code = run_pipeline()
        log.info("scheduled_job_complete", job="fetch_rates", exit_code=exit_code)
    except Exception as e:
        log.exception("scheduled_job_failed", job="fetch_rates", error=str(e))


def job_check_alerts():
    """Wrapper: evaluate alerts + catch + log."""
    log.info("scheduled_job_started", job="check_alerts")
    try:
        evaluator = AlertEvaluator()
        triggered, skipped = evaluator.run()
        log.info(
            "scheduled_job_complete",
            job="check_alerts",
            triggered=triggered,
            skipped=skipped,
        )
    except Exception as e:
        log.exception("scheduled_job_failed", job="check_alerts", error=str(e))


def main() -> int:
    scheduler = BlockingScheduler(timezone="UTC")
    
    # Daily fetch at 12:30 UTC (after NBP fixing ~12:00)
    scheduler.add_job(
        job_fetch_rates,
        CronTrigger(hour=12, minute=30),
        id="fetch_rates_daily",
        replace_existing=True,
    )
    
    # Hourly alert check
    scheduler.add_job(
        job_check_alerts,
        IntervalTrigger(hours=1),
        id="check_alerts_hourly",
        replace_existing=True,
    )
    
    log.info(
        "scheduler_started",
        jobs=[j.id for j in scheduler.get_jobs()],
        timezone="UTC",
        now=datetime.utcnow().isoformat(),
    )
    
    # Optional: run jobs once on startup (handy for first deploy)
    log.info("running_initial_fetch")
    job_fetch_rates()
    job_check_alerts()
    
    try:
        scheduler.start()  # blocks forever
    except (KeyboardInterrupt, SystemExit):
        log.info("scheduler_stopped")
        return 0
    
    return 0


if __name__ == "__main__":
    sys.exit(main())