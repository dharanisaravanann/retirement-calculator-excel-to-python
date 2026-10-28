"""Streamlit front end for the retirement balance model. Run: streamlit run app.py"""

import altair as alt
import pandas as pd
import streamlit as st

from model import Inputs, project

NAVY = "#1F4E79"
ORANGE = "#E8833A"
MUTED = "#5A6472"

st.set_page_config(page_title="Retirement Balance Calculator", layout="wide")


def short_money(value: float) -> str:
    """$2.39M, $303K, $950 style figures for headline numbers."""
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 1_000_000:
        return f"{sign}${value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{sign}${value / 1_000:.0f}K"
    return f"{sign}${value:,.0f}"


def md_money(value: float) -> str:
    """short_money for st.markdown/st.caption, where a bare $ starts LaTeX maths."""
    return short_money(value).replace("$", "\\$")


@st.cache_data
def reconciliation_report():
    """Live Python-vs-Excel check, or None if the Excel values aren't available."""
    try:
        from test_reconciliation import EXCEL, TEST_CASES, TOLERANCE, compare
    except Exception:
        return None, None
    report = pd.DataFrame([compare(name, EXCEL[name]) for name in TEST_CASES])
    numeric = ["Python final balance", "Excel final balance", "Max abs difference"]
    report[numeric] = report[numeric].astype(float)
    return report, TOLERANCE


# ---- Sidebar inputs ----
with st.sidebar:
    st.subheader("Your details")
    current_age = st.number_input("Current age", 18, 80, 30)
    retirement_age = st.number_input("Retirement age", 19, 90, 67)
    starting_balance = st.number_input("Starting balance ($)", 0, 10_000_000, 50_000, step=5_000)
    annual_contribution = st.number_input("Annual contribution, year 1 ($)", 0, 1_000_000, 10_000, step=1_000)

    with st.expander("Market and fee assumptions"):
        expected_return = st.slider("Expected annual return (%)", -5.0, 15.0, 7.0, 0.25)
        fee_rate = st.slider("Annual fee (% of balance)", 0.0, 3.0, 1.0, 0.05)
        contribution_growth = st.slider("Contribution growth (% a year)", 0.0, 10.0, 3.0, 0.25)

    st.subheader("Scenario")
    return_drop = st.slider("Lower the return by (percentage points)", 0.0, 5.0, 2.0, 0.25)

# ---- Calculations ----
base_inputs = Inputs(int(current_age), int(retirement_age), float(starting_balance), float(annual_contribution),
                     expected_return / 100, fee_rate / 100, contribution_growth / 100)
low_inputs = Inputs(**{**base_inputs.__dict__, "expected_return": (expected_return - return_drop) / 100})

st.title("Retirement balance calculator")
st.caption("Illustrative model, not financial advice. It doesn't predict your actual balance. "
           "Default figures are made-up examples.")

try:
    base = project(base_inputs)
    low = project(low_inputs)
except ValueError as err:
    st.error(str(err))
    st.stop()

base_final = base["Closing balance"].iloc[-1]
low_final = low["Closing balance"].iloc[-1]
gap = base_final - low_final
base_label = f"Base case ({expected_return:.2f}%)"
low_label = f"Lower return ({expected_return - return_drop:.2f}%)"

# ---- Summary ----
st.markdown(
    f"Based on these assumptions, the balance at {retirement_age} is about "
    f"<span style='color:{NAVY};font-weight:600'>{md_money(base_final)}</span>. "
    f"If returns are {return_drop:g} points lower, it's about "
    f"<span style='color:#C8642A;font-weight:600'>{md_money(low_final)}</span>.",
    unsafe_allow_html=True,
)

c1, c2, c3 = st.columns(3)
c1.metric(f"Balance at {retirement_age}", short_money(base_final), border=True)
c2.metric("With lower return", short_money(low_final),
          f"-{short_money(gap)} ({-gap / base_final:.1%})" if base_final else None, border=True)
c3.metric("Total fees paid", short_money(base["Fees"].sum()), border=True)

tab_projection, tab_scenario, tab_table, tab_method = st.tabs(
    ["Projection", "Scenario comparison", "Year-by-year table", "Method and testing"]
)

# ---- Projection chart ----
with tab_projection:
    wide = pd.DataFrame({
        "Age": base["Age"],
        "Base": base["Closing balance"],
        "Low": low["Closing balance"],
    })
    long = pd.concat([
        base.assign(Scenario=base_label),
        low.assign(Scenario=low_label),
    ])
    x = alt.X("Age:Q", title="Age (start of year)", scale=alt.Scale(nice=False),
              axis=alt.Axis(grid=False, tickMinStep=1, format="d"))
    y_axis = alt.Axis(gridColor="#EEF1F4", labelExpr=(
        "datum.value >= 1e6 ? '$' + format(datum.value / 1e6, '.1f') + 'M'"
        " : datum.value >= 1e3 ? '$' + format(datum.value / 1e3, '.0f') + 'K' : '$0'"))
    colors = alt.Scale(domain=[base_label, low_label], range=[NAVY, ORANGE])

    band = alt.Chart(wide).mark_area(color=NAVY, opacity=0.08).encode(
        x=x, y=alt.Y("Low:Q"), y2="Base:Q", tooltip=alt.value(None)
    )
    lines = alt.Chart(long).mark_line(strokeWidth=2.5).encode(
        x=x,
        y=alt.Y("Closing balance:Q", title=None, axis=y_axis),
        color=alt.Color("Scenario:N", scale=colors, legend=alt.Legend(orient="top", title=None)),
        tooltip=["Scenario", "Age", alt.Tooltip("Closing balance:Q", title="Balance", format="$,.0f")],
    )
    end_points = long.groupby("Scenario", as_index=False).last()
    end_points["Label"] = end_points["Closing balance"].map(short_money)
    labels = alt.Chart(end_points).mark_text(align="left", dx=6, fontSize=12, fontWeight=600).encode(
        x="Age:Q", y="Closing balance:Q", text="Label:N",
        color=alt.Color("Scenario:N", scale=colors, legend=None),
    )
    chart = (band + lines + labels).properties(height=400).configure_view(strokeWidth=0)
    st.altair_chart(chart, use_container_width=True)
    st.caption(f"The shaded area is the cost of a {return_drop:g} point lower return: {md_money(gap)} less at "
               f"{retirement_age}. Small changes in the return assumption compound over time.")

# ---- Scenario comparison ----
with tab_scenario:
    def summary(df):
        return {
            f"Balance at {retirement_age}": df["Closing balance"].iloc[-1],
            "Total contributions": df["Contribution"].sum(),
            "Total investment return": df["Investment return"].sum(),
            "Total fees": df["Fees"].sum(),
        }

    comparison = pd.DataFrame({base_label: summary(base), low_label: summary(low)})
    comparison["Difference"] = comparison[low_label] - comparison[base_label]
    st.dataframe(comparison.style.format(lambda v: f"-${-v:,.0f}" if v < 0 else f"${v:,.0f}"),
                 use_container_width=True)
    st.caption("Contributions are the same in both scenarios. The whole difference comes from lower investment "
               "returns, partly offset by lower fees on a smaller balance.")

# ---- Year-by-year table ----
with tab_table:
    st.dataframe(
        base.style.format("${:,.0f}", subset=list(base.columns[2:])),
        use_container_width=True,
        hide_index=True,
        height=420,
    )
    st.download_button("Download table as CSV", base.round(2).to_csv(index=False),
                       "retirement_projection.csv", "text/csv")

# ---- Method and testing ----
report, tolerance = reconciliation_report()
with tab_method:
    st.markdown(
        "**Each year:**\n"
        "1. The contribution is added at the start of the year. It grows by the contribution growth rate each year.\n"
        "2. The expected return is applied to (opening balance + contribution).\n"
        "3. Fees are deducted as a percentage of the balance after returns.\n"
        "4. The closing balance becomes next year's opening balance.\n\n"
        "The same method is built in Excel (`retirement_model.xlsx`) and Python (`model.py`), and the two are "
        "compared cell by cell for every year in five test cases."
    )
    if report is not None:
        st.dataframe(
            report.style.format({
                "Python final balance": "${:,.2f}",
                "Excel final balance": "${:,.2f}",
                "Max abs difference": "${:.5f}",
            }),
            use_container_width=True,
            hide_index=True,
        )
    st.markdown("**Not modelled:** tax, inflation, insurance, fixed-dollar fees, contribution caps and "
                "year-to-year variation in returns.")

# ---- Footer ----
st.divider()
if report is not None:
    passed = int((report["Max abs difference"] < tolerance).sum())
    ok = passed == len(report)
    bg, fg = ("#E3F1E8", "#1E6B3A") if ok else ("#FBE9E7", "#B3261E")
    badge = (f"<span style='background:{bg};color:{fg};border-radius:6px;padding:2px 8px'>"
             f"{passed}/{len(report)} checks match Excel</span>")
    note = f"Reconciled within &#36;{tolerance} · made-up example numbers"
else:
    badge, note = "", "Excel reconciliation values not found · made-up example numbers"
st.markdown(f"<div style='font-size:0.85rem;color:{MUTED}'>{badge} &nbsp;{note}</div>", unsafe_allow_html=True)
