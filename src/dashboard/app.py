"""Streamlit dashboard entry point."""
# isort: skip_file

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

import streamlit as st  # noqa: E402
from datetime import date, timedelta  # noqa: E402
import plotly.express as px  # noqa: E402
from decimal import Decimal  # noqa: E402

from src.dashboard.queries import (  # noqa: E402
    get_active_currencies,
    get_latest_rates,
    get_rates_for_period,
    get_top_movers,
    get_alert_rules,
    get_alert_history,
    create_alert_rule,
    toggle_alert_rule,
    delete_alert_rule,
)

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

# ============================================================
# === ALERTS SECTION ===
# ============================================================
st.divider()
st.header("🔔 Price Alerts")
st.caption("Get notified when currency rates cross your thresholds. "
           "Alerts evaluated by `python -m src.scheduler.check_alerts`.")


# --- Add new alert form ---
with st.expander("➕ Add new alert", expanded=False):
    with st.form("add_alert_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            alert_currency = st.selectbox(
                "Currency",
                options=all_currencies,
                help="Must exist in `currencies` table",
            )
            alert_operator = st.selectbox(
                "Trigger when rate is",
                options=["lt", "le", "gt", "ge"],
                format_func=lambda x: {
                    "lt": "< (less than)",
                    "le": "≤ (less or equal to)",
                    "gt": "> (greater than)",
                    "ge": "≥ (greater or equal to)",
                }[x],
            )

        with col2:
            alert_threshold = st.number_input(
                "Threshold (PLN)",
                min_value=0.0,
                step=0.01,
                format="%.4f",
                help="Trigger value in Polish złoty",
            )
            alert_label = st.text_input(
                "Label (optional)",
                placeholder="e.g. 'USD cheap for travel'",
                max_chars=100,
            )

        submitted = st.form_submit_button("Create alert", type="primary")

        if submitted:
            if alert_threshold <= 0:
                st.error("⚠️ Threshold must be greater than 0.")
            else:
                try:
                    new_id = create_alert_rule(
                        currency_code=alert_currency,
                        threshold_pln=Decimal(str(alert_threshold)),
                        operator=alert_operator,
                        label=alert_label.strip() or None,
                    )

            # === IMMEDIATE EVALUATION ===
                    from src.scheduler.check_alerts import AlertEvaluator
                    evaluator = AlertEvaluator()
                    triggered_alert = evaluator.evaluate_single_rule(new_id)

                    if triggered_alert:
                        st.success(
                            f"✅ Alert #{new_id} created AND **triggered immediately**! "
                            f"Current rate {float(triggered_alert['rate_at_trigger']):.4f} PLN "
                            f"matches your threshold."
                        )
                    # Clear history cache so new alert appears
                        get_alert_history.clear()
                    else:
                        st.success(
                            f"✅ Alert #{new_id} created. "
                            f"Will be evaluated by next scheduler run."
                        )

                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to create alert: {e}")


# --- Active + disabled rules ---
st.subheader("Your rules")

rules_df = get_alert_rules(active_only=False)

if rules_df.empty:
    st.info("No alert rules yet. Add one above ☝️")
else:
    OPERATOR_SYMBOLS = {"lt": "<", "le": "≤", "gt": ">", "ge": "≥"}

    for _, row in rules_df.iterrows():
        rule_id = int(row["id"])
        currency = row["currency_code"]
        operator_str = OPERATOR_SYMBOLS[row["operator"]]
        threshold = float(row["threshold_pln"])
        label = row["label"] or "—"
        is_active = bool(row["active"])

        cols = st.columns([4, 1, 1])

        with cols[0]:
            status_icon = "🟢" if is_active else "🔴"
            st.write(
                f"{status_icon} **{currency} {operator_str} {threshold:.4f} PLN** "
                f"— {label}"
            )

        with cols[1]:
            btn_label = "Disable" if is_active else "Enable"
            if st.button(btn_label, key=f"toggle_{rule_id}", use_container_width=True):
                toggle_alert_rule(rule_id, active=not is_active)
                st.rerun()

        with cols[2]:
            if st.button("🗑️ Delete", key=f"delete_{rule_id}", use_container_width=True):
                delete_alert_rule(rule_id)
                st.rerun()


# --- Recent alerts history ---
st.subheader("Recent alerts")

history_df = get_alert_history(limit=20)

if history_df.empty:
    st.info(
        "No alerts triggered yet. "
        "Run `python -m src.scheduler.check_alerts` to evaluate active rules "
        "against latest rates."
    )
else:
    display_history = history_df.copy()

    # Map operator codes to symbols
    OPERATOR_SYMBOLS = {"lt": "<", "le": "≤", "gt": ">", "ge": "≥"}
    display_history["operator"] = display_history["operator"].map(
        OPERATOR_SYMBOLS)

    # Format numerics
    display_history["threshold_pln"] = display_history["threshold_pln"].apply(
        lambda x: f"{x:.4f}"
    )
    display_history["rate_at_trigger"] = display_history["rate_at_trigger"].apply(
        lambda x: f"{x:.4f}"
    )

    # Friendlier column names
    display_history = display_history.rename(columns={
        "rule_id": "Rule ID",
        "currency_code": "Currency",
        "operator": "Op.",
        "threshold_pln": "Threshold",
        "label": "Label",
        "rate_at_trigger": "Rate at trigger",
        "effective_date": "Effective date",
        "triggered_at": "Triggered at",
    })

    st.dataframe(
        display_history,
        use_container_width=True,
        hide_index=True,
    )
