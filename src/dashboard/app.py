"""Streamlit dashboard entry point."""
# isort: skip_file

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

import streamlit as st  # noqa: E402
from datetime import date, timedelta  # noqa: E402
from src.dashboard.queries import (  # noqa: E402
    get_active_currencies,
    get_latest_rates,
    get_rates_for_period,
    get_top_movers,
)
import plotly.express as px  # noqa: E402

# === Page setup ===
st.set_page_config(
    page_title="NBP Tracker",
    page_icon="💱",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stMetric {
        background: linear-gradient(135deg, #B3E5FC 0%, #E1F5FE 100%);
        padding: 1rem;
        border-radius: 16px;
        box-shadow: 0 4px 12px rgba(0, 153, 204, 0.15);
    }
    .stPlotlyChart {
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0, 153, 204, 0.1);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("💱 NBP Exchange Rate Tracker")
st.caption("Monitor selected currency rates from National Bank of Poland (NBP) API")


# === Sidebar filters ===
with st.sidebar:
    st.header("Filters")

    all_currencies = get_active_currencies()

    selected_currencies = st.multiselect(
        "Currencies",
        options=all_currencies,
        default=["USD", "EUR", "JPY"],
        help="Select currencies to display",
    )

    time_range = st.select_slider(
        "Time range",
        options=["7d", "30d", "90d", "1y"],
        value="30d",
    )

    normalize = st.toggle(
        "Normalize (% change from start)",
        value=False,
        help="Show relative changes instead of absolute PLN values",
    )

    st.divider()
    st.caption("Data source: api.nbp.pl")


# Map time range to days
DAYS_MAP = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}
days = DAYS_MAP[time_range]
from_date = date.today() - timedelta(days=days)
to_date = date.today()


# === Empty state ===
if not selected_currencies:
    st.warning("⚠️ Select at least one currency in the sidebar.")
    st.stop()


# === KPI cards (latest rates) ===
st.subheader("Latest rates")

latest = get_latest_rates(tuple(selected_currencies))

if latest.empty:
    st.warning("No rates in database. Run `python -m src.main` to load data.")
    st.stop()

# 4 columns side-by-side
kpi_cols = st.columns(min(len(selected_currencies), 4))
for idx, currency in enumerate(selected_currencies[:4]):
    row = latest[latest["currency_code"] == currency]
    if not row.empty:
        rate = float(row.iloc[0]["rate_pln"])
        eff_date = row.iloc[0]["effective_date"]
        with kpi_cols[idx]:
            st.metric(
                label=f"{currency}/PLN",
                value=f"{rate:.4f}",
                help=f"As of {eff_date}",
            )


# === Main line chart ===
st.subheader(f"Rates over {time_range}")

rates_df = get_rates_for_period(
    currencies=tuple(selected_currencies),
    from_date=from_date,
    to_date=to_date,
)

data_per_currency = rates_df.groupby("currency_code").size()
sparse_currencies = data_per_currency[data_per_currency < 2].index.tolist()
if sparse_currencies:
    st.info(
        f"⚠️ {', '.join(sparse_currencies)} have <2 historical data points. "
        f"Run: `python scripts/load_history.py --currencies {','.join(sparse_currencies)}`"
    )

if rates_df.empty:
    st.info(
        f"No data for selected period. Try loading history: `python scripts/load_history.py --days {days}`")
else:
    # Optionally normalize to % change from first day
    if normalize:
        rates_df = rates_df.copy()
        rates_df["rate_pln"] = rates_df.groupby("currency_code")["rate_pln"].transform(
            lambda x: (x / x.iloc[0] - 1) * 100
        )
        y_label = "% change vs start"
    else:
        y_label = "PLN per unit"

    fig = px.line(
        rates_df,
        x="effective_date",
        y="rate_pln",
        color="currency_code",
        labels={"effective_date": "Date",
                "rate_pln": y_label, "currency_code": "Currency"},
        hover_data=["table_no"],
    )
    fig.update_layout(
        hovermode="x unified",  # hover shows ALL currencies at given X
        legend_title_text="Currency",
        height=450,
    )
    st.plotly_chart(fig, use_container_width=True)


# === Top movers table ===
st.subheader(f"Top movers ({time_range})")

movers = get_top_movers(tuple(selected_currencies), days=days)

if movers.empty:
    st.info("Not enough data to calculate movers.")
else:
    # Format for display
    movers_display = movers.copy()
    movers_display["pct_change"] = movers_display["pct_change"].apply(
        lambda x: f"{x:+.2f}%" if x is not None else "N/A"
    )
    movers_display.columns = ["Currency",
                              "Oldest rate", "Latest rate", "% change"]
    st.dataframe(movers_display, use_container_width=True, hide_index=True)


# === Footer ===
st.divider()
st.caption(
    "💡 Tip: hover over chart to see exact values. "
    "Click on legend items to hide/show currencies."
)
