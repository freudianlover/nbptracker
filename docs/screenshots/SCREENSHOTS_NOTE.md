## Note Regarding Dashboard Screenshots

If you notice that the line charts under the **"Rates over 30d"** section are empty or do not display trend lines in the screenshots inside `docs/screenshots/`, this is expected behavior and represents the **initial application state (Day 1)**.

### Why is the chart empty?

* **Minimum Data Requirement:** To render a continuous line chart, the visualization component requires **at least two distinct historical data points (days)**.
* **Daily API Ingestion:** Because the ETL pipeline fetches data from the National Bank of Poland (NBP) API once per day, running the application for the first time provides only a single data point for the current day. 

The dashboard explicitly handles this by displaying a warning banner:
> ⚠️ *CNY, HKD, USD have < 2 historical data points. Run: `python scripts/load_history.py --currencies CNY,HKD,USD`*

### How to Populate the Charts

If you want to view the full interactive charts immediately instead of waiting for the daily cron jobs to accumulate data over consecutive days, you can backfill the database using the provided utility script.

Run the following command in your terminal:

```bash
python scripts/load_history.py --days 90 --currencies CNY,HKD,USD
