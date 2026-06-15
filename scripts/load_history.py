"""
One-off script: backfill historical NBP rates for selected currencies.

Usage:
    python scripts/load_history.py
    python scripts/load_history.py --days 90 --currencies USD,EUR,JPY,CNY
"""
# isort: skip_file
import argparse
from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from src.load.postgres import PostgresLoader  # noqa: E402
from src.extract.nbp import NbpClient  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Backfill historical rates")
    parser.add_argument("--days", type=int, default=30,
                        help="Number of days to backfill")
    parser.add_argument(
        "--currencies",
        type=str,
        default="USD,EUR,JPY",
        help="Comma-separated currency codes",
    )
    args = parser.parse_args()

    currencies = [c.strip().upper() for c in args.currencies.split(",")]
    print(
        f"Backfilling {len(currencies)} currencies for {args.days} days: {currencies}")

    client = NbpClient(user_agent="nbptracker/0.1 by KarolMasiak")
    all_rates = []
    for code in currencies:
        try:
            rates = client.fetch_currency_history(
                code, number_of_days=args.days)
            print(f"  Fetched {len(rates)} rates for {code}")
            all_rates.extend(rates)
        except Exception as e:
            print(f"  Error fetching {code}: {e}")

    if not all_rates:
        print("No rates to load.")
        return

    loader = PostgresLoader()
    with loader.connection() as conn:
        inserted, updated = loader.upsert_rates(conn, all_rates)
        print(f"\nTotal: inserted={inserted}, updated={updated}")


if __name__ == "__main__":
    main()
