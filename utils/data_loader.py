# utils/data_loader.py
"""
Data loading and cleaning functions for the HPRTC Run-5 Excel workbook.

The source workbook has messy, hand-built sheets (merged cells, headers that
don't start on row 0, multiple tables per sheet, etc). Every `clean_*`
function below is responsible for locating the real header row inside one
sheet and returning a tidy DataFrame. If your workbook uses different sheet
names or slightly different header wording, adjust the string matches in
each function accordingly.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Dict

import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)


def load_raw_sheets(excel_path: str | Path) -> Dict[str, pd.DataFrame]:
    """Load every sheet as a raw DataFrame (header=None, nothing parsed)."""
    xls = pd.ExcelFile(excel_path)
    return {name: pd.read_excel(xls, sheet_name=name, header=None) for name in xls.sheet_names}


# ----------------------------------------------------------------------
# 1. Oil Compositional Analysis
# ----------------------------------------------------------------------
def clean_oil_composition(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a clean DataFrame with columns:
    Component, Pre-Run, Trap 1, Trap 2, Trap 3, Trap 4, Spill-Over
    """
    # Find the header row
    header_row = None
    for i, row in df.iterrows():
        if str(row[0]).strip().lower() == "components":
            header_row = i
            break
    if header_row is None:
        raise ValueError("Could not find 'Components' header in Oil Compositional Analysis")

    data = df.iloc[header_row + 1:].copy()
    base_cols = ["Component", "Pre-Run", "Trap 1", "Trap 2", "Trap 3", "Trap 4", "Spill-Over"]
    data.columns = base_cols + list(data.columns[len(base_cols):])
    data = data[base_cols]

    # Keep only real components (C1 ... C36+)
    data = data[data["Component"].notna()]
    data = data[~data["Component"].astype(str).str.contains("Total|MW|Oil Type", case=False, na=False)]

    # Convert to numeric
    for col in data.columns[1:]:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    data = data.reset_index(drop=True)
    return data


def get_oil_mw(df: pd.DataFrame) -> pd.Series:
    """Extract molecular weights from anywhere in the raw sheet."""
    mw = {}
    for i, row in df.iterrows():
        val = str(row[0]).strip() if pd.notna(row[0]) else ""
        if "Pre-Exp Oil" in val or "Pre-Run" in val:
            mw["Pre-Run"] = pd.to_numeric(row[1], errors="coerce")
        elif "Trap 1" in val:
            mw["Trap 1"] = pd.to_numeric(row[1], errors="coerce")
        elif "Trap 2" in val:
            mw["Trap 2"] = pd.to_numeric(row[1], errors="coerce")
        elif "Trap 3" in val:
            mw["Trap 3"] = pd.to_numeric(row[1], errors="coerce")
        elif "Trap 4" in val:
            mw["Trap 4"] = pd.to_numeric(row[1], errors="coerce")
        elif "Spill-Over" in val:
            mw["Spill-Over"] = pd.to_numeric(row[1], errors="coerce")
    return pd.Series(mw, name="MW (g/mol)")


# ----------------------------------------------------------------------
# 2. Temperature / Meter data (HPRTC_Run_5_Lanwa_Meter)
# ----------------------------------------------------------------------
def clean_meter_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the main time-series sheet that contains:
    Date, Time, Run-time, all TCs, pressures, flows, etc.
    """
    header_row = None
    for i, row in df.iterrows():
        if str(row[0]).strip().lower() == "date" and "time" in str(row[1]).lower():
            header_row = i
            break
    if header_row is None:
        raise ValueError("Could not find header in HPRTC_Run_5_Lanwa_Meter")

    data = df.iloc[header_row:].copy()
    data.columns = data.iloc[0]
    data = data.iloc[1:].reset_index(drop=True)
    data.columns = [str(c).strip() for c in data.columns]

    if "Run-time, hrs" in data.columns:
        data["Run-time, hrs"] = pd.to_numeric(data["Run-time, hrs"], errors="coerce")

    tc_cols = [c for c in data.columns if "TC" in str(c).upper() or "Internal" in str(c)]
    for c in tc_cols:
        data[c] = pd.to_numeric(data[c], errors="coerce")

    data = data.dropna(how="all")
    return data


# ----------------------------------------------------------------------
# 3. GC Value Table / With GCD (cleaned gas composition)
# ----------------------------------------------------------------------
def clean_gc_value_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the GC Value Table or 'With GCD' sheet.
    Returns time series of mole% for each component.
    """
    header_row = None
    for i, row in df.iterrows():
        if "Run time" in str(row[0]) or "Run-Time" in str(row[0]):
            header_row = i
            break
    if header_row is None:
        for i, row in df.iterrows():
            if str(row[0]).strip().lower() in ["run-time", "hours"]:
                header_row = i
                break
    if header_row is None:
        raise ValueError("Could not locate header in GC sheet")

    data = df.iloc[header_row:].copy()
    data.columns = data.iloc[0]
    data = data.iloc[1:].reset_index(drop=True)
    data.columns = [str(c).strip() for c in data.columns]

    time_col = data.columns[0]
    data[time_col] = pd.to_numeric(data[time_col], errors="coerce")

    for c in data.columns[1:]:
        data[c] = pd.to_numeric(data[c], errors="coerce")

    data = data.dropna(subset=[time_col])
    data = data.rename(columns={time_col: "Run-time, hrs"})
    return data


# ----------------------------------------------------------------------
# 4. Gas Production History (rates in g/h-g sand)
# ----------------------------------------------------------------------
def clean_gas_production_history(df: pd.DataFrame) -> pd.DataFrame:
    """Clean 'Gas Production History' or 'Gas Production History-Trendlin'."""
    header_row = 0
    for i, row in df.iterrows():
        if "T Avg" in str(row[0]) or "1/T" in str(row[1]):
            header_row = i
            break

    data = df.iloc[header_row:].copy()
    data.columns = data.iloc[0]
    data = data.iloc[1:].reset_index(drop=True)
    data.columns = [str(c).strip() for c in data.columns]

    for c in data.columns:
        data[c] = pd.to_numeric(data[c], errors="coerce")

    data = data.dropna(how="all")
    return data


# ----------------------------------------------------------------------
# 5. Arrhenius / Gas Production Rates Table
# ----------------------------------------------------------------------
def clean_arrhenius_table(df: pd.DataFrame) -> pd.DataFrame:
    """Parse the 'Gas Production Rates Table' sheet."""
    records = []
    current_comp = None
    for i, row in df.iterrows():
        comp = row[0]
        temp_range = row[1]
        rate_expr = row[2]

        if pd.notna(comp) and str(comp).strip():
            current_comp = str(comp).strip()

        if current_comp and pd.notna(temp_range) and pd.notna(rate_expr):
            records.append({
                "Component": current_comp,
                "Temperature Range (°C)": str(temp_range).strip(),
                "Rate Expression": str(rate_expr).strip(),
            })
    return pd.DataFrame(records)


# ----------------------------------------------------------------------
# 6. Packed Saturations (summary numbers)
# ----------------------------------------------------------------------
def extract_packed_saturations(df: pd.DataFrame) -> dict:
    """Extract key saturation numbers into a simple dictionary."""
    result = {}
    for i, row in df.iterrows():
        desc = str(row[0]).strip() if pd.notna(row[0]) else ""
        val = row[1]
        if "Oil Saturation" in desc:
            result["Oil Saturation"] = pd.to_numeric(val, errors="coerce")
        elif "Brine Sturation" in desc or "Brine Saturation" in desc:
            result["Brine Saturation"] = pd.to_numeric(val, errors="coerce")
        elif "Gas Saturation" in desc:
            result["Gas Saturation"] = pd.to_numeric(val, errors="coerce")
        elif "native zones porosity" in desc.lower():
            result["Native Porosity"] = pd.to_numeric(val, errors="coerce")
    return result


# ----------------------------------------------------------------------
# Master loader
# ----------------------------------------------------------------------
def load_hprtc_data(excel_path: str | Path) -> dict:
    """
    Main entry point.
    Returns a dictionary of cleaned DataFrames / objects ready for the dashboard.
    Any sheet that fails to parse is skipped (not fatal) so the rest of the
    app can still run; check `cleaned["_errors"]` to see what was skipped.
    """
    excel_path = Path(excel_path)
    raw = load_raw_sheets(excel_path)

    cleaned: dict = {}
    errors: dict = {}

    def _try(key, fn, *args):
        try:
            cleaned[key] = fn(*args)
        except Exception as exc:  # noqa: BLE001 - want to keep the app alive
            errors[key] = str(exc)

    # Oil composition
    if "Oil Compositional Analysis" in raw:
        _try("oil_comp", clean_oil_composition, raw["Oil Compositional Analysis"])
        _try("oil_mw", get_oil_mw, raw["Oil Compositional Analysis"])

    # Meter / temperature data
    meter_key = next((k for k in raw if "Lanwa_Meter" in k or "HPRTC_Run" in k), None)
    if meter_key:
        _try("meter", clean_meter_data, raw[meter_key])

    # GC data - prefer the cleaned versions
    for key in ["With GCD", "GC Value Table", "GC VLOOKUP TABLE"]:
        if key in raw:
            _try("gc", clean_gc_value_table, raw[key])
            break

    # Gas production rates
    for key in ["Gas Production History-Trendlin", "Gas Production History"]:
        if key in raw:
            _try("gas_rates", clean_gas_production_history, raw[key])
            break

    # Arrhenius expressions
    if "Gas Production Rates Table" in raw:
        _try("arrhenius_expr", clean_arrhenius_table, raw["Gas Production Rates Table"])

    # Saturations
    if "Packed Saturations" in raw:
        _try("saturations", extract_packed_saturations, raw["Packed Saturations"])

    cleaned["_raw"] = raw
    cleaned["_errors"] = errors

    return cleaned


# ----------------------------------------------------------------------
# Quick test
# ----------------------------------------------------------------------
if __name__ == "__main__":
    data = load_hprtc_data("data/HPRTC_Run-5.xlsx")
    print("Loaded keys:", [k for k in data.keys() if not k.startswith("_")])
    if data.get("_errors"):
        print("Sheets that failed to parse:", data["_errors"])
    if "oil_comp" in data:
        print("\nOil composition head:")
        print(data["oil_comp"].head(10))
    if "meter" in data:
        print("\nMeter columns:", data["meter"].columns.tolist()[:10])
    if "gc" in data:
        print("\nGC columns:", data["gc"].columns.tolist()[:8])
