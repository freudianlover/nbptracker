"""
One-off script: fetch real NBP API responses and save as test fixtures.

Run once to populate tests/fixtures/ with sample JSON files.
Re-run if NBP API shape changes (rare).

Usage:
    python scripts/generate_fixtures.py
"""
import json
from pathlib import Path

import requests


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
HEADERS = {"User-Agent": "nbptracker/0.1 by KarolMasiak"}

REQUESTS = {
    "nbp_usd_last_10.json": "https://api.nbp.pl/api/exchangerates/rates/A/USD/last/10/?format=json",
    "nbp_table_a.json": "https://api.nbp.pl/api/exchangerates/tables/A/?format=json",
    "nbp_eur_range.json": "https://api.nbp.pl/api/exchangerates/rates/A/EUR/2026-05-01/2026-05-27/?format=json",
    "nbp_jpy_single.json": "https://api.nbp.pl/api/exchangerates/rates/A/JPY/?format=json",
}


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    for filename, url in REQUESTS.items():
        print(f"Fetching {filename} ...")
        response = requests.get(url, headers=HEADERS, timeout=10)

        if response.status_code != 200:
            print(f"  ✗ HTTP {response.status_code} — skipped")
            continue

        path = FIXTURES_DIR / filename
        # json.dumps z indent=2 dla czytelności gdy ktoś otwiera w edytorze
        path.write_text(json.dumps(response.json(),
                        indent=2, ensure_ascii=False))
        print(f"  ✓ Saved to {path}")

    print("\nDone. Fixtures ready for pytest.")


if __name__ == "__main__":
    main()
