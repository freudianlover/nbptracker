"""
Standalone alert evaluator script.

Reads active rules from `alert_rules`, evaluates each against latest rate
in `exchange_rates_daily`, and inserts triggered alerts into `alerts_sent`
with no-spam protection (24h cooldown per rule).

Usage:
    python -m src.scheduler.check_alerts
    python -m src.scheduler.check_alerts --cooldown 48   # custom no-spam window
"""
from src.loger import configure_logger
from src.load.exceptions import PostgresError
from src.load.postgres import PostgresLoader
from src.extract.models import ExchangeRate
import structlog
import argparse
import sys
from datetime import date
from decimal import Decimal
from typing import Optional

from dotenv import load_dotenv
load_dotenv()


configure_logger()
log = structlog.get_logger()


class AlertEvaluator:
    """
    Evaluates active alert rules against latest exchange rates.

    Usage:
        evaluator = AlertEvaluator(spam_window_hours=24)
        triggered, skipped = evaluator.run()
    """

    OPERATORS = {
        "gt": lambda rate, threshold: rate > threshold,
        "lt": lambda rate, threshold: rate < threshold,
        "ge": lambda rate, threshold: rate >= threshold,
        "le": lambda rate, threshold: rate <= threshold,
    }

    def __init__(self, spam_window_hours: int = 24):
        self.spam_window_hours = spam_window_hours
        self.loader = PostgresLoader()

    def get_active_rules(self, conn) -> list[dict]:
        """Fetch all active alert rules."""
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, currency_code, threshold_pln, operator, label
                FROM alert_rules
                WHERE active = TRUE;
                """
            )
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def get_latest_rate(self, conn, currency_code: str) -> Optional[tuple[Decimal, date]]:
        """
        Get most recent rate for currency.

        Returns (rate_pln, effective_date) or None if no rates exist.
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT rate_pln, effective_date
                FROM exchange_rates_daily
                WHERE currency_code = %s
                ORDER BY effective_date DESC
                LIMIT 1;
                """,
                (currency_code,),
            )
            row = cur.fetchone()
            return (row[0], row[1]) if row else None

    def was_triggered_recently(self, conn, rule_id: int) -> bool:
        """Check if rule fired in last `spam_window_hours` hours."""
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM alerts_sent
                WHERE rule_id = %s
                  AND triggered_at > NOW() - INTERVAL '%s hours'
                LIMIT 1;
                """,
                (rule_id, self.spam_window_hours),
            )
            return cur.fetchone() is not None

    def evaluate_rule(self, rule: dict, current_rate: Decimal) -> bool:
        """Apply operator to (current_rate, threshold). Returns True if triggered."""
        operator_fn = self.OPERATORS[rule["operator"]]
        return operator_fn(current_rate, rule["threshold_pln"])

    def record_alert(
        self, conn, rule_id: int, rate: Decimal, effective_date: date
    ) -> None:
        """Insert triggered alert into alerts_sent."""
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO alerts_sent (rule_id, rate_at_trigger, effective_date)
                VALUES (%s, %s, %s);
                """,
                (rule_id, rate, effective_date),
            )

    def run(self) -> tuple[int, int]:
        """
        Evaluate all active rules.

        Returns:
            (triggered_count, skipped_count)
        """
        triggered = 0
        skipped = 0

        with self.loader.connection() as conn:
            rules = self.get_active_rules(conn)
            log.info("evaluator_started", active_rules=len(rules))

            for rule in rules:
                rule_id = rule["id"]
                currency = rule["currency_code"]
                operator = rule["operator"]
                threshold = rule["threshold_pln"]
                label = rule["label"] or f"{currency} {operator} {threshold}"

                # 1. Get latest rate
                latest = self.get_latest_rate(conn, currency)
                if latest is None:
                    log.warning(
                        "no_rate_data",
                        rule_id=rule_id,
                        currency=currency,
                    )
                    skipped += 1
                    continue

                rate, effective_date = latest

                # 2. Evaluate
                if not self.evaluate_rule(rule, rate):
                    log.debug(
                        "rule_not_triggered",
                        rule_id=rule_id,
                        label=label,
                        rate=float(rate),
                        threshold=float(threshold),
                    )
                    continue

                # 3. No-spam check
                if self.was_triggered_recently(conn, rule_id):
                    log.info(
                        "rule_skipped_cooldown",
                        rule_id=rule_id,
                        label=label,
                    )
                    skipped += 1
                    continue

                # 4. Record alert
                self.record_alert(conn, rule_id, rate, effective_date)
                log.info(
                    "ALERT_TRIGGERED",
                    rule_id=rule_id,
                    label=label,
                    rate=float(rate),
                    threshold=float(threshold),
                    operator=operator,
                    effective_date=effective_date.isoformat(),
                )
                triggered += 1

        log.info("evaluator_complete", triggered=triggered, skipped=skipped)
        return triggered, skipped


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate alert rules and record triggers")
    parser.add_argument(
        "--cooldown",
        type=int,
        default=24,
        help="No-spam window in hours (default: 24)",
    )
    args = parser.parse_args()

    try:
        evaluator = AlertEvaluator(spam_window_hours=args.cooldown)
        triggered, skipped = evaluator.run()
        print(
            f"\n→ Triggered: {triggered} | Skipped (cooldown/no-data): {skipped}")
        return 0

    except PostgresError as e:
        log.error("postgres_failure", error=str(e))
        return 1
    except Exception as e:
        log.exception("unexpected_error", error=str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
