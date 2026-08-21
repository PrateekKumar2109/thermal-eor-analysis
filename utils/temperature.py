# utils/temperature.py
"""Temperature profile plotting and endothermic/combustion front velocity analysis."""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go


def get_tc_columns(meter_df: pd.DataFrame) -> List[str]:
    """Return list of thermocouple columns."""
    candidates = []
    for c in meter_df.columns:
        c_str = str(c).upper()
        if any(x in c_str for x in ["TC", "INTERNAL", "TEMP"]):
            if not any(x in c_str for x in ["TIME", "RUN", "DATE", "PRESS", "FLOW", "RATE"]):
                candidates.append(c)
    return candidates


def prepare_temperature_data(meter_df: pd.DataFrame) -> pd.DataFrame:
    """Clean and standardize temperature data. Ensures 'Run-time, hrs' + numeric TC columns."""
    df = meter_df.copy()

    time_candidates = [c for c in df.columns if "run-time" in str(c).lower() or "runtime" in str(c).lower()]
    if time_candidates:
        df = df.rename(columns={time_candidates[0]: "Run-time, hrs"})
    elif "Run-time, hrs" not in df.columns:
        raise ValueError("Could not find Run-time column")

    df["Run-time, hrs"] = pd.to_numeric(df["Run-time, hrs"], errors="coerce")
    df = df.dropna(subset=["Run-time, hrs"])

    tc_cols = get_tc_columns(df)
    for c in tc_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.sort_values("Run-time, hrs").reset_index(drop=True)


def calculate_front_velocity(
    df: pd.DataFrame,
    tc_cols: List[str],
    threshold_temp: float = 300.0,
    positions_mm: Optional[Dict[str, float]] = None,
) -> pd.DataFrame:
    """
    Estimate endothermic/combustion front arrival time at each TC and
    compute an approximate front velocity.

    positions_mm: optional dict mapping TC name -> axial position in mm
                  (e.g. from the injection end). Required for velocity.
    """
    records = []

    for tc in tc_cols:
        series = df[["Run-time, hrs", tc]].dropna()
        if series.empty:
            continue

        above = series[series[tc] >= threshold_temp]
        arrival = above["Run-time, hrs"].iloc[0] if not above.empty else np.nan

        records.append({
            "Thermocouple": tc,
            "Arrival time (h)": arrival,
            "Max T (°C)": series[tc].max(),
            "Final T (°C)": series[tc].iloc[-1] if len(series) > 0 else np.nan,
        })

    result = pd.DataFrame(records)

    if positions_mm:
        result["Position (mm)"] = result["Thermocouple"].map(positions_mm)
        result = result.sort_values("Position (mm)")
        result["Δt (h)"] = result["Arrival time (h)"].diff()
        result["Δx (mm)"] = result["Position (mm)"].diff()
        result["Velocity (mm/h)"] = result["Δx (mm)"] / result["Δt (h)"]

    return result


def plot_temperature_profiles(
    df: pd.DataFrame,
    tc_cols: List[str],
    highlight_front: bool = True,
    threshold_temp: float = 300.0,
    title: str = "Temperature Profiles vs Run Time",
) -> go.Figure:
    """Interactive multi-line temperature plot."""
    fig = go.Figure()

    colors = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
        "#aec7e8", "#ffbb78", "#98df8a", "#ff9896",
    ]

    for i, tc in enumerate(tc_cols):
        fig.add_trace(
            go.Scatter(
                x=df["Run-time, hrs"], y=df[tc], mode="lines", name=tc,
                line=dict(width=2.2, color=colors[i % len(colors)]),
                hovertemplate=f"<b>{tc}</b><br>Time: %{{x:.2f}} h<br>T: %{{y:.1f}} °C<extra></extra>",
            )
        )

    if highlight_front:
        fig.add_hline(
            y=threshold_temp, line_dash="dash", line_color="rgba(200,0,0,0.6)",
            annotation_text=f"Front threshold ({threshold_temp}°C)", annotation_position="top left",
        )

    fig.update_layout(
        title=title,
        xaxis_title="Run-time (hours)",
        yaxis_title="Temperature (°C)",
        height=600,
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="v", yanchor="top", y=0.99, xanchor="left", x=1.01, bgcolor="rgba(255,255,255,0.8)"),
        margin=dict(r=180),
    )
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="rgba(0,0,0,0.08)")
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="rgba(0,0,0,0.08)")

    return fig


def plot_temperature_heatmap(
    df: pd.DataFrame,
    tc_cols: List[str],
    positions_mm: Optional[Dict[str, float]] = None,
) -> go.Figure:
    """Heatmap of temperature evolution (TC position vs time)."""
    plot_df = df[["Run-time, hrs"] + tc_cols].set_index("Run-time, hrs")

    if positions_mm:
        ordered = sorted([c for c in tc_cols if c in positions_mm], key=lambda x: positions_mm[x])
        ordered += [c for c in tc_cols if c not in ordered]
        plot_df = plot_df[ordered]
    else:
        ordered = tc_cols

    fig = go.Figure(
        data=go.Heatmap(
            z=plot_df.T.values, x=plot_df.index, y=ordered,
            colorscale="Jet", colorbar=dict(title="T (°C)"),
            hovertemplate="Time: %{x:.2f} h<br>TC: %{y}<br>T: %{z:.1f} °C<extra></extra>",
        )
    )
    fig.update_layout(
        title="Temperature Heatmap (Thermocouple vs Time)",
        xaxis_title="Run-time (hours)",
        yaxis_title="Thermocouple",
        height=500,
        template="plotly_white",
    )
    return fig
