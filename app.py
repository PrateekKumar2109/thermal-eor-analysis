# app.py
"""  interactive analysis dashboard."""

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.data_loader import load__data
from utils.arrhenius import (
    fit_arrhenius,
    get_available_components,
    plot_arrhenius,
    prepare_arrhenius_data,
)
from utils.temperature import (
    calculate_front_velocity,
    get_tc_columns,
    plot_temperature_heatmap,
    plot_temperature_profiles,
    prepare_temperature_data,
)

# ------------------------------------------------------------------
# Page config
# ------------------------------------------------------------------
st.set_page_config(
    page_title="  Dashboard",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_PATH = Path(__file__).parent / "data" / "_Run-5.xlsx"


# ------------------------------------------------------------------
# Load data (cached)
# ------------------------------------------------------------------
@st.cache_data(show_spinner="Loading Excel data...")
def get_data(path: str):
    return load__data(path)


if not DATA_PATH.exists():
    st.title("  Dashboard")
    st.error(
        f"No workbook found at `{DATA_PATH.relative_to(Path(__file__).parent)}`.\n\n"
        "Copy your _Run.xlsx file into the `data/` folder (or run "
        "`python generate_sample_data.py` to try the app with sample data), then reload."
    )
    st.stop()

data = get_data(str(DATA_PATH))

# ------------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------------
st.sidebar.title("🔥  ")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    [
        "Overview",
        "Oil Composition",
        "Packing & Saturations",
        "Temperature Profiles",
        "Flue Gas (GC)",
        "Gas Production & Kinetics",
        "Mass Balance",
        "Report",
    ],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.caption(f"Data source: {DATA_PATH.name}")
if st.sidebar.button("🔄 Reload data"):
    st.cache_data.clear()
    st.rerun()

if data.get("_errors"):
    with st.sidebar.expander(f"⚠️ {len(data['_errors'])} sheet(s) failed to parse"):
        for sheet, err in data["_errors"].items():
            st.caption(f"**{sheet}**: {err}")


def _safe_metric(col, label, value, fmt=None, suffix=""):
    """Render a metric that gracefully falls back to '–' for missing/NaN values."""
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            raise ValueError
        text = f"{value:{fmt}}{suffix}" if fmt else f"{value}{suffix}"
    except (ValueError, TypeError):
        text = "–"
    col.metric(label, text)


# ==================================================================
# PAGE: Overview
# ==================================================================
if page == "Overview":
    st.title("  — Overview")
    st.markdown("High Pressure Ramped Temperature Cracking / Oxidation Test")

    col1, col2, col3, col4 = st.columns(4)

    oil_mw = data.get("oil_mw")
    pre_run_mw = oil_mw.get("Pre-Run") if isinstance(oil_mw, pd.Series) else None
    _safe_metric(col1, "Oil MW (Pre-Run)", pre_run_mw, fmt=".1f", suffix=" g/mol")

    sat = data.get("saturations", {})
    oil_sat = sat.get("Oil Saturation")
    _safe_metric(col2, "Oil Saturation", oil_sat * 100 if oil_sat is not None else None, fmt=".1f", suffix=" %")

    meter = data.get("meter")
    max_time = meter["Run-time, hrs"].max() if meter is not None and "Run-time, hrs" in meter.columns else None
    _safe_metric(col3, "Total Run Time", max_time, fmt=".1f", suffix=" h")

    col4.metric("Status", "Data Loaded" if not data.get("_errors") else "Loaded (with warnings)")

    st.markdown("---")
    st.subheader("Available Data Sections")
    st.markdown(
        """
        - **Oil Composition** — Mole% of C1-C36+ in Pre-run, Traps & Spill-over
        - **Temperature Profiles** — All thermocouples vs time + front velocity
        - **Flue Gas (GC)** — Time series of O₂, N₂, CH₄, CO, CO₂, C₂+, H₂...
        - **Gas Production & Kinetics** — Arrhenius analysis of hydrocarbon production rates
        - **Mass Balance** — Injected vs produced gas & oil recovery
        """
    )

    with st.expander("Raw sheet list"):
        st.write([k for k in data.get("_raw", {}).keys()])


# ==================================================================
# PAGE: Oil Composition
# ==================================================================
elif page == "Oil Composition":
    st.title("Oil Compositional Analysis")

    if "oil_comp" not in data:
        st.error("Oil Composition sheet not found or failed to clean.")
        st.stop()

    oil = data["oil_comp"]
    mw = data.get("oil_mw", pd.Series(dtype=float))

    st.subheader("Molecular Weight")
    if isinstance(mw, pd.Series) and not mw.empty:
        mw_df = mw.reset_index()
        mw_df.columns = ["Oil Type", "MW (g/mol)"]
        st.dataframe(mw_df, width="stretch", hide_index=True)

        fig_mw = px.bar(
            mw_df, x="Oil Type", y="MW (g/mol)", text="MW (g/mol)", color="Oil Type",
            title="Molecular Weight of Oils",
        )
        fig_mw.update_traces(texttemplate="%{text:.1f}", textposition="outside")
        st.plotly_chart(fig_mw, width="stretch")
    else:
        st.info("No molecular weight data found.")

    st.subheader("Mole % Distribution")

    oil_melt = oil.melt(id_vars="Component", var_name="Sample", value_name="Mole %")
    oil_melt = oil_melt[oil_melt["Mole %"].notna()]

    all_components = oil["Component"].astype(str).tolist()
    default_components = [
        c for c in all_components
        if c.startswith(("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", "C15", "C20", "C25", "C30", "C36"))
    ] or all_components[: min(10, len(all_components))]

    components_to_show = st.multiselect(
        "Select components to display", options=all_components, default=default_components,
    )

    if components_to_show:
        plot_df = oil_melt[oil_melt["Component"].isin(components_to_show)]
        fig = px.bar(
            plot_df, x="Component", y="Mole %", color="Sample", barmode="group",
            title="Oil Composition Comparison", height=500,
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, width="stretch")

    with st.expander("Full Composition Table"):
        numeric_cols = oil.columns[1:]
        st.dataframe(oil.style.format("{:.3f}", subset=numeric_cols, na_rep="–"), width="stretch")


# ==================================================================
# PAGE: Packing & Saturations
# ==================================================================
elif page == "Packing & Saturations":
    st.title("Reactor Packing & Saturations")

    if "saturations" in data:
        sat = data["saturations"]
        st.subheader("Final Packed Saturations")
        cols = st.columns(3)
        _safe_metric(cols[0], "Oil Saturation", sat.get("Oil Saturation", 0) * 100 if sat.get("Oil Saturation") is not None else None, fmt=".2f", suffix=" %")
        _safe_metric(cols[1], "Brine Saturation", sat.get("Brine Saturation", 0) * 100 if sat.get("Brine Saturation") is not None else None, fmt=".2f", suffix=" %")
        _safe_metric(cols[2], "Gas Saturation", sat.get("Gas Saturation", 0) * 100 if sat.get("Gas Saturation") is not None else None, fmt=".2f", suffix=" %")

        if "Native Porosity" in sat:
            _safe_metric(st, "Native Sand Porosity", sat["Native Porosity"] * 100, fmt=".2f", suffix=" %")
    else:
        st.info("Saturation summary not extracted yet.")

    st.markdown("---")
    st.info("Detailed packing design tables (zones, heights, frac sand masses, etc.) can be added here.")


# ==================================================================
# PAGE: Temperature Profiles
# ==================================================================
elif page == "Temperature Profiles":
    st.title("Temperature Profiles & Front Velocity")

    if "meter" not in data:
        st.error("Meter / temperature data not found.")
        st.stop()

    try:
        meter = prepare_temperature_data(data["meter"])
    except ValueError as e:
        st.error(str(e))
        st.stop()

    tc_cols = get_tc_columns(meter)

    if not tc_cols:
        st.warning("No thermocouple columns detected.")
        st.write("Available columns:", meter.columns.tolist())
        st.stop()

    st.sidebar.markdown("### Temperature Controls")
    selected_tcs = st.sidebar.multiselect(
        "Select Thermocouples", options=tc_cols, default=tc_cols[:8] if len(tc_cols) > 8 else tc_cols,
    )
    threshold = st.sidebar.number_input(
        "Front detection threshold (°C)", min_value=50.0, max_value=800.0, value=300.0, step=10.0,
    )
    show_heatmap = st.sidebar.checkbox("Show Temperature Heatmap", value=True)

    # Optional: axial positions (mm from injection end) for velocity calc.
    # Fill this in with your real TC locations to unlock the velocity column.
    default_positions: dict = {}

    if not selected_tcs:
        st.warning("Please select at least one thermocouple.")
        st.stop()

    fig_profiles = plot_temperature_profiles(meter, selected_tcs, highlight_front=True, threshold_temp=threshold)
    st.plotly_chart(fig_profiles, width="stretch")

    st.subheader("Front Arrival & Approximate Velocity")
    front_df = calculate_front_velocity(
        meter, selected_tcs, threshold_temp=threshold, positions_mm=default_positions or None,
    )
    fmt = {"Arrival time (h)": "{:.2f}", "Max T (°C)": "{:.1f}", "Final T (°C)": "{:.1f}"}
    if "Velocity (mm/h)" in front_df.columns:
        fmt["Velocity (mm/h)"] = "{:.1f}"
    st.dataframe(front_df.style.format(fmt, na_rep="–"), width="stretch", hide_index=True)
    st.caption(
        "Arrival time = first time the thermocouple exceeds the threshold temperature. "
        "Velocity is only calculated when TC axial positions are supplied in `default_positions`."
    )

    if show_heatmap:
        st.subheader("Temperature Evolution Heatmap")
        st.plotly_chart(plot_temperature_heatmap(meter, selected_tcs), width="stretch")

    with st.expander("Temperature data (first 20 rows)"):
        st.dataframe(meter[["Run-time, hrs"] + selected_tcs].head(20), width="stretch")


# ==================================================================
# PAGE: Flue Gas (GC)
# ==================================================================
elif page == "Flue Gas (GC)":
    st.title("Flue Gas Composition (GC)")

    if "gc" not in data:
        st.error("GC data not found.")
        st.stop()

    gc = data["gc"]
    st.write(f"Data points: {len(gc)}")

    comp_cols = [c for c in gc.columns if c != "Run-time, hrs"]
    default_gc = [c for c in ["O2", "N2", "CH4", "CO", "CO2", "H2"] if c in comp_cols][:4] or comp_cols[:4]
    selected = st.multiselect("Select components", options=comp_cols, default=default_gc)

    if selected:
        fig = go.Figure()
        for col in selected:
            fig.add_trace(go.Scatter(x=gc["Run-time, hrs"], y=gc[col], mode="lines", name=col))
        fig.update_layout(
            title="Flue Gas Composition vs Run Time",
            xaxis_title="Run-time (h)",
            yaxis_title="Mole %",
            height=550,
            hovermode="x unified",
            template="plotly_white",
        )
        st.plotly_chart(fig, width="stretch")

    with st.expander("Raw GC table (first 50 rows)"):
        st.dataframe(gc.head(50), width="stretch")


# ==================================================================
# PAGE: Gas Production & Kinetics
# ==================================================================
elif page == "Gas Production & Kinetics":
    st.title("Gas Production Rates & Arrhenius Analysis")

    if "gas_rates" not in data:
        st.error("Gas production history data not found.")
        st.stop()

    rates = data["gas_rates"]
    components = get_available_components(rates)

    if not components:
        st.warning("No usable rate columns found.")
        st.stop()

    st.sidebar.markdown("### Arrhenius Controls")
    component = st.sidebar.selectbox("Component", components, index=0)

    all_T = rates["T Avg"].dropna() if "T Avg" in rates.columns else pd.Series([300.0, 460.0])
    t_min_default, t_max_default = float(all_T.min()), float(all_T.max())

    col_t1, col_t2 = st.sidebar.columns(2)
    t_min = col_t1.number_input("T min (°C)", value=round(t_min_default, 0), min_value=0.0, max_value=800.0, step=5.0)
    t_max = col_t2.number_input("T max (°C)", value=round(t_max_default, 0), min_value=0.0, max_value=800.0, step=5.0)

    show_rate_plot = st.sidebar.checkbox("Show Rate vs T plot", value=True)

    try:
        df_prep = prepare_arrhenius_data(rates, component)
        fit = fit_arrhenius(df_prep, t_min=t_min, t_max=t_max)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Activation Energy (Ea)", f"{fit['Ea_kJ_mol']:.1f} kJ/mol")
        c2.metric("Pre-exponential (A)", f"{fit['A']:.3e}")
        c3.metric("R²", f"{fit['r_squared']:.4f}")
        c4.metric("Points used", f"{fit['n_points']}")

        st.caption(f"Fitted temperature window: {fit['t_min']:.1f} - {fit['t_max']:.1f} °C")

        fig = plot_arrhenius(fit, component, show_rate_plot=show_rate_plot)
        st.plotly_chart(fig, width="stretch")

        with st.expander("Data used for the fit"):
            st.dataframe(
                fit["data"][["T_C", "inv_T", "rate", "ln_rate"]].style.format(
                    {"T_C": "{:.1f}", "inv_T": "{:.6f}", "rate": "{:.4e}", "ln_rate": "{:.4f}"}
                ),
                width="stretch",
            )
    except ValueError as e:
        st.error(f"Could not perform fit: {e}")
        st.info("Try widening the temperature window or choosing another component.")

    if "arrhenius_expr" in data:
        st.markdown("---")
        st.subheader("Rate Expressions from Original Excel")
        st.dataframe(data["arrhenius_expr"], width="stretch", hide_index=True)


# ==================================================================
# PAGE: Mass Balance
# ==================================================================
elif page == "Mass Balance":
    st.title("Mass Balance")
    st.info("Mass balance calculations will be expanded later.")
    st.write(
        "This section will show injected N₂ vs produced gas, oil recovery from traps, "
        "and carbon / hydrogen balance once the relevant sheet-cleaning function is added "
        "to `utils/data_loader.py` (mirroring the pattern used for the other sheets)."
    )


# ==================================================================
# PAGE: Report
# ==================================================================
elif page == "Report":
    st.title("Summary Report")

    meter = data.get("meter")
    max_t = None
    if meter is not None:
        tc_cols = get_tc_columns(meter)
        if tc_cols:
            numeric = meter[tc_cols].apply(pd.to_numeric, errors="coerce")
            max_t = numeric.max().max()

    oil = data.get("oil_comp")
    oil_recovered = None
    if oil is not None:
        trap_cols = [c for c in ["Trap 1", "Trap 2", "Trap 3", "Trap 4"] if c in oil.columns]
        if trap_cols:
            oil_recovered = oil[trap_cols].sum().sum()

    col1, col2 = st.columns(2)
    _safe_metric(col1, "Maximum Temperature Reached", max_t, fmt=".1f", suffix=" °C")
    _safe_metric(col2, "Total Mole % Recovered in Traps", oil_recovered, fmt=".1f", suffix=" %")

    st.markdown("---")
    st.markdown(
        """
        ### Notes
        - Visit **Gas Production & Kinetics** for activation energy (Ea) and pre-exponential
          factor (A) per component.
        - Visit **Temperature Profiles** for front arrival times and velocity.
        - A "Download PDF / Excel report" button can be added here once the summary
          content above is finalized.
        """
    )
