# nbptracker
NBP Exchange Rates Tracker with notification system
# NBPTracker — Polish Exchange Rate Pipeline

A personal data engineering project: automated ingestion of Polish National 
Bank (NBP) exchange rates with time-series storage, interactive dashboard, 
and threshold-based alerts. Built to monitor PLN exchange rates while 
planning international travel.

## Why this exists

I've been planning a trip to Asia and wanted a simple way to track when 
key exchange rates (EUR, USD, CNY, JPY) hit favorable levels. I built 
NBPTracker to demonstrate end-to-end data engineering fundamentals: REST 
API ingestion, normalized PostgreSQL warehousing, scheduled orchestration, 
and interactive visualization.

## Status

**v1 (in progress, target 2026-06-17)**: NBP API ingestion → PostgreSQL 
time-series → Streamlit dashboard with multi-currency comparison + 
threshold alerts.

## Tech stack

- Python 3.11 + pandas
- PostgreSQL 16 (time-series schema with proper indexing)
- APScheduler (daily refresh at 12:30 after NBP fixing)
- Streamlit + Plotly (interactive dashboard)
- Docker + docker-compose
- pytest (unit tests for API client)

## Quickstart

(coming when Docker setup is done)

## API exploration

##NBP API requests are documented as a Postman collection in 
[`HERE`](docs/exchange_rates_nbp.postman_collection.json). 
Import into Postman to explore endpoints and sample responses.
