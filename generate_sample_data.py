"""
Generate a synthetic data/HPRTC_Run-5.xlsx so the dashboard can be run and
explored immediately, without needing the real lab workbook.

The sheet layout intentionally mimics a messy real-world export (title rows,
header rows that don't start at row 0, extra summary rows mixed in) so it
exercises the same parsing logic in utils/data_loader.py that the real file
will need. Replace data/HPRTC_Run-5.xlsx with your actual workbook when
you're ready -- if your sheet/column names differ, adjust the string
matches in utils/data_loader.py to match.

Run:
    python generate_sample_data.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
OUT_PATH = Path(__file__).parent / "data" / "HPRTC_Run-5.xlsx"

R = 8.314  # J/mol.K


# ----------------------------------------------------------------------
# 1. Oil Compositional Analysis
# ----------------------------------------------------------------------
def build_oil_composition_sheet() -> pd.DataFrame:
    carbon_numbers = [f"C{i}" for i in range(1, 11)] + ["C15", "C20", "C25", "C30", "C36+"]
    n = len(carbon_numbers)

    # Rough log-decaying mole% distributions per sample
    def dist():
        vals = rng.uniform(0.5, 1.0, n) * np.exp(-np.arange(n) / 6)
        return np.round(100 * vals / vals.sum(), 3)

    rows = [["Oil Compositional Analysis - Run 5"], [None],
            ["Components", "Pre-Run", "Trap 1", "Trap 2", "Trap 3", "Trap 4", "Spill-Over"]]

    samples = {name: dist() for name in ["Pre-Run", "Trap 1", "Trap 2", "Trap 3", "Trap 4", "Spill-Over"]}
    for i, comp in enumerate(carbon_numbers):
        rows.append([comp] + [samples[name][i] for name in samples])

    rows.append(["Total"] + [round(sum(samples[name]), 2) for name in samples])
    rows.append([None])
    rows.append(["Pre-Exp Oil MW (g/mol)", 245.6])
    rows.append(["Trap 1 MW (g/mol)", 232.1])
    rows.append(["Trap 2 MW (g/mol)", 228.4])
    rows.append(["Trap 3 MW (g/mol)", 219.7])
    rows.append(["Trap 4 MW (g/mol)", 205.3])
    rows.append(["Spill-Over MW (g/mol)", 190.8])

    max_len = max(len(r) for r in rows)
    rows = [r + [None] * (max_len - len(r)) for r in rows]
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# 2. HPRTC_Run_5_Lanwa_Meter (temperature time series)
# ----------------------------------------------------------------------
def build_meter_sheet(n_tc: int = 10, n_points: int = 300, run_hours: float = 24.0) -> pd.DataFrame:
    header = ["Date", "Time", "Run-time, hrs"] + [f"TC {i} - Internal {i}" for i in range(1, n_tc + 1)]
    rows = [["HPRTC Run-5 Meter Data"], [None], header]

    t = np.linspace(0, run_hours, n_points)
    # Simulate a thermal front sweeping through the pack: each TC warms up
    # at a progressively later time, mimicking front propagation.
    for row_i in range(n_points):
        date_str = "2026-01-01"
        time_str = f"{int(t[row_i]):02d}:{int((t[row_i] % 1) * 60):02d}"
        row = [date_str, time_str, round(float(t[row_i]), 3)]
        for tc in range(n_tc):
            onset = 2.0 + tc * 1.8          # hrs before this TC starts heating
            rise_rate = 60.0                 # deg C / hr during heat-up
            baseline = 25.0
            peak = 480.0 + rng.normal(0, 5)
            elapsed = t[row_i] - onset
            if elapsed <= 0:
                temp = baseline + rng.normal(0, 0.5)
            else:
                temp = baseline + min(peak - baseline, rise_rate * elapsed)
                temp += rng.normal(0, 1.5)
            row.append(round(float(temp), 2))
        rows.append(row)

    max_len = max(len(r) for r in rows)
    rows = [r + [None] * (max_len - len(r)) for r in rows]
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# 3. GC Value Table (flue gas composition time series)
# ----------------------------------------------------------------------
def build_gc_value_table(n_points: int = 120, run_hours: float = 24.0) -> pd.DataFrame:
    components = ["O2", "N2", "CH4", "CO", "CO2", "H2", "C2H6", "C3H8"]
    header = ["Run-Time"] + components
    rows = [["GC Value Table - Flue Gas Composition"], [None], header]

    t = np.linspace(0.1, run_hours, n_points)
    for ti in t:
        # crude synthetic profile: O2/N2 dominate early, combustion products rise mid-run
        combustion_frac = np.clip((ti - 4) / 12, 0, 1)
        o2 = max(0.5, 20.9 * (1 - combustion_frac) + rng.normal(0, 0.3))
        n2 = max(50, 78.1 - 5 * combustion_frac + rng.normal(0, 0.5))
        co2 = 2 + 10 * combustion_frac + rng.normal(0, 0.4)
        co = 0.2 + 1.5 * combustion_frac * np.exp(-((ti - 12) ** 2) / 20) + rng.normal(0, 0.05)
        ch4 = 0.1 + 0.8 * np.exp(-((ti - 10) ** 2) / 15) + rng.normal(0, 0.03)
        h2 = 0.05 + 0.4 * np.exp(-((ti - 14) ** 2) / 25) + rng.normal(0, 0.02)
        c2h6 = 0.05 + 0.3 * np.exp(-((ti - 9) ** 2) / 12) + rng.normal(0, 0.02)
        c3h8 = 0.02 + 0.15 * np.exp(-((ti - 8) ** 2) / 10) + rng.normal(0, 0.01)
        rows.append([round(ti, 2)] + [round(max(0, v), 3) for v in [o2, n2, ch4, co, co2, h2, c2h6, c3h8]])

    max_len = max(len(r) for r in rows)
    rows = [r + [None] * (max_len - len(r)) for r in rows]
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# 4 & 5. Gas Production History + Rate expressions (Arrhenius-consistent)
# ----------------------------------------------------------------------
def build_gas_production_history() -> pd.DataFrame:
    """
    Synthesize rate data that actually obeys the Arrhenius law so the
    fitting module has something real to recover:
        rate = A * exp(-Ea / (R*T))
    """
    kinetics = {
        "CH4": dict(A=5.0e6, Ea=110_000),
        "C2H6": dict(A=2.0e6, Ea=118_000),
        "C3H8": dict(A=8.0e5, Ea=125_000),
        "C4H10": dict(A=3.0e5, Ea=132_000),
    }

    t_c = np.linspace(300, 460, 20)
    t_k = t_c + 273.15
    inv_t = 1 / t_k

    header = ["T Avg", "1/T Avg"] + list(kinetics.keys())
    rows = [["Gas Production History (rates, g/h-g sand)"], [None], header]

    for i in range(len(t_c)):
        row = [round(float(t_c[i]), 1), round(float(inv_t[i]), 6)]
        for comp, k in kinetics.items():
            rate = k["A"] * np.exp(-k["Ea"] / (R * t_k[i]))
            noisy_rate = rate * (1 + rng.normal(0, 0.06))
            row.append(round(float(max(noisy_rate, 1e-8)), 8))
        rows.append(row)

    max_len = max(len(r) for r in rows)
    rows = [r + [None] * (max_len - len(r)) for r in rows]
    return pd.DataFrame(rows)


def build_arrhenius_expr_table() -> pd.DataFrame:
    rows = [
        ["Gas Production Rates Table"],
        [None],
        ["CH4", "300-460 C", "rate = 5.0e6 * exp(-110000/RT)"],
        [None, "R2 = 0.98", None],
        ["C2H6", "300-460 C", "rate = 2.0e6 * exp(-118000/RT)"],
        [None, "R2 = 0.97", None],
        ["C3H8", "300-460 C", "rate = 8.0e5 * exp(-125000/RT)"],
        [None, "R2 = 0.96", None],
        ["C4H10", "300-460 C", "rate = 3.0e5 * exp(-132000/RT)"],
        [None, "R2 = 0.95", None],
    ]
    max_len = max(len(r) for r in rows)
    rows = [r + [None] * (max_len - len(r)) for r in rows]
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# 6. Packed Saturations
# ----------------------------------------------------------------------
def build_packed_saturations_sheet() -> pd.DataFrame:
    rows = [
        ["Packed Saturations - Run 5"],
        [None],
        ["Oil Saturation", 0.35],
        ["Brine Saturation", 0.25],
        ["Gas Saturation", 0.40],
        ["Native zones porosity", 0.32],
    ]
    max_len = max(len(r) for r in rows)
    rows = [r + [None] * (max_len - len(r)) for r in rows]
    return pd.DataFrame(rows)


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT_PATH, engine="openpyxl") as writer:
        build_oil_composition_sheet().to_excel(writer, sheet_name="Oil Compositional Analysis", header=False, index=False)
        build_meter_sheet().to_excel(writer, sheet_name="HPRTC_Run_5_Lanwa_Meter", header=False, index=False)
        build_gc_value_table().to_excel(writer, sheet_name="GC Value Table", header=False, index=False)
        build_gas_production_history().to_excel(writer, sheet_name="Gas Production History", header=False, index=False)
        build_arrhenius_expr_table().to_excel(writer, sheet_name="Gas Production Rates Table", header=False, index=False)
        build_packed_saturations_sheet().to_excel(writer, sheet_name="Packed Saturations", header=False, index=False)

    print(f"Sample workbook written to: {OUT_PATH}")


if __name__ == "__main__":
    main()
