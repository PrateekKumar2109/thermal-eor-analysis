# utils/arrhenius.py
"""Arrhenius kinetics fitting (ln(rate) vs 1/T) and plotting."""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import linregress

R = 8.314  # J/mol.K


def prepare_arrhenius_data(
    rates_df: pd.DataFrame,
    component: str,
    temp_col: str = "T Avg",
    inv_temp_col: str = "1/T Avg",
) -> pd.DataFrame:
    """
    Extract temperature and rate for a given component.
    Returns a clean DataFrame with T(C), T(K), 1/T, rate, ln(rate).
    """
    if component not in rates_df.columns:
        raise ValueError(
            f"Component '{component}' not found in rates data. "
            f"Available: {[c for c in rates_df.columns if c not in [temp_col, inv_temp_col]]}"
        )
    if temp_col not in rates_df.columns or inv_temp_col not in rates_df.columns:
        raise ValueError(
            f"Expected temperature columns '{temp_col}' / '{inv_temp_col}' not found. "
            f"Available columns: {list(rates_df.columns)}"
        )

    df = rates_df[[temp_col, inv_temp_col, component]].copy()
    df = df.dropna()
    df = df[df[component] > 0]  # only positive rates for ln

    df = df.rename(columns={temp_col: "T_C", inv_temp_col: "inv_T", component: "rate"})

    df["T_K"] = df["T_C"] + 273.15
    df["ln_rate"] = np.log(df["rate"])

    return df.reset_index(drop=True)


def fit_arrhenius(
    df: pd.DataFrame,
    t_min: Optional[float] = None,
    t_max: Optional[float] = None,
) -> Dict:
    """
    Linear regression of ln(rate) vs 1/T.

    Returns a dict with Ea_kJ_mol, A, slope, intercept, r_squared, p_value,
    std_err, n_points, t_min, t_max, data, fitted_line.
    """
    data = df.copy()

    if t_min is not None:
        data = data[data["T_C"] >= t_min]
    if t_max is not None:
        data = data[data["T_C"] <= t_max]

    if len(data) < 3:
        raise ValueError("Need at least 3 points for a meaningful Arrhenius fit.")

    x = data["inv_T"].values
    y = data["ln_rate"].values

    slope, intercept, r_value, p_value, std_err = linregress(x, y)

    Ea = -slope * R / 1000  # kJ/mol
    A = np.exp(intercept)   # pre-exponential factor

    inv_T_line = np.linspace(x.min(), x.max(), 100)
    ln_rate_line = intercept + slope * inv_T_line
    fitted = pd.DataFrame({
        "inv_T": inv_T_line,
        "ln_rate_fit": ln_rate_line,
        "rate_fit": np.exp(ln_rate_line),
        "T_C": 1 / inv_T_line - 273.15,
    })

    return {
        "Ea_kJ_mol": Ea,
        "A": A,
        "slope": slope,
        "intercept": intercept,
        "r_squared": r_value ** 2,
        "p_value": p_value,
        "std_err": std_err,
        "n_points": len(data),
        "t_min": data["T_C"].min(),
        "t_max": data["T_C"].max(),
        "data": data,
        "fitted_line": fitted,
    }


def plot_arrhenius(fit_result: Dict, component: str, show_rate_plot: bool = True) -> go.Figure:
    """Professional Arrhenius plot (ln(rate) vs 1/T), optionally with rate-vs-T alongside."""
    data = fit_result["data"]
    fitted = fit_result["fitted_line"]

    if show_rate_plot:
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=(f"Arrhenius Plot — {component}", f"Rate vs Temperature — {component}"),
            horizontal_spacing=0.12,
        )
        col_main = 1
    else:
        fig = go.Figure()
        col_main = None

    def add_trace(trace, col):
        if show_rate_plot:
            fig.add_trace(trace, row=1, col=col)
        else:
            fig.add_trace(trace)

    add_trace(
        go.Scatter(
            x=data["inv_T"], y=data["ln_rate"], mode="markers", name="Experimental",
            marker=dict(size=9, color="#1f77b4", line=dict(width=1, color="white")),
            hovertemplate="1/T = %{x:.5f}<br>ln(rate) = %{y:.3f}<extra></extra>",
        ),
        col_main,
    )
    add_trace(
        go.Scatter(
            x=fitted["inv_T"], y=fitted["ln_rate_fit"], mode="lines", name="Linear fit",
            line=dict(color="#d62728", width=2.5),
            hovertemplate="Fit: ln(rate) = %{y:.3f}<extra></extra>",
        ),
        col_main,
    )

    annotation_text = (
        f"E<sub>a</sub> = {fit_result['Ea_kJ_mol']:.1f} kJ/mol<br>"
        f"A = {fit_result['A']:.3e}<br>"
        f"R² = {fit_result['r_squared']:.4f}<br>"
        f"n = {fit_result['n_points']} points<br>"
        f"T range: {fit_result['t_min']:.0f}-{fit_result['t_max']:.0f} °C"
    )
    ann_kwargs = dict(
        text=annotation_text, x=0.05, y=0.95, showarrow=False, align="left",
        bgcolor="rgba(255,255,255,0.85)", bordercolor="#333", borderwidth=1,
        borderpad=6, font=dict(size=12),
    )
    if show_rate_plot:
        fig.add_annotation(xref="x domain", yref="y domain", row=1, col=1, **ann_kwargs)
    else:
        fig.add_annotation(xref="x domain", yref="y domain", **ann_kwargs)

    if show_rate_plot:
        fig.add_trace(
            go.Scatter(
                x=data["T_C"], y=data["rate"], mode="markers", name="Experimental rate",
                marker=dict(size=9, color="#1f77b4"), showlegend=False,
                hovertemplate="T = %{x:.1f} °C<br>rate = %{y:.3e}<extra></extra>",
            ),
            row=1, col=2,
        )
        fig.add_trace(
            go.Scatter(
                x=fitted["T_C"], y=fitted["rate_fit"], mode="lines", name="Fitted rate",
                line=dict(color="#d62728", width=2.5), showlegend=False,
            ),
            row=1, col=2,
        )
        fig.update_xaxes(title_text="Temperature (°C)", row=1, col=2)
        fig.update_yaxes(title_text="Rate (g/h.g sand)", type="log", row=1, col=2)
        fig.update_xaxes(title_text="1/T (1/K)", row=1, col=1)
        fig.update_yaxes(title_text="ln(rate)", row=1, col=1)
    else:
        fig.update_xaxes(title_text="1/T (1/K)")
        fig.update_yaxes(title_text="ln(rate)")

    fig.update_layout(
        height=520,
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=80, b=60),
    )
    return fig


def get_available_components(rates_df: pd.DataFrame) -> List[str]:
    """Return list of rate columns (exclude temperature columns)."""
    exclude = {"T Avg", "1/T Avg", "T_C", "inv_T", "T_K"}
    return [c for c in rates_df.columns if c not in exclude and rates_df[c].notna().sum() > 5]
