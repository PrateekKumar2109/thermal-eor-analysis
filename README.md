# HPRTC Run-5 Dashboard

Interactive Streamlit dashboard that replaces the HPRTC Run-5 Excel analysis
workbook with a browsable, filterable, zoomable web app: oil composition,
temperature/front-velocity profiles, flue gas (GC) composition, Arrhenius
kinetics fitting, packing/saturations, mass balance, and a summary report.

## Project structure

```
hprtc_dashboard/
├── app.py                    # Main Streamlit app (all pages)
├── generate_sample_data.py   # Builds a synthetic workbook for a quick test run
├── requirements.txt
├── data/
│   └── HPRTC_Run-5.xlsx      # Put your real workbook here (not included)
└── utils/
    ├── data_loader.py        # Loads + cleans every sheet
    ├── arrhenius.py           # Arrhenius (ln rate vs 1/T) fitting + plots
    └── temperature.py         # Temperature profiles + front-velocity calc
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run it

**Option A — with your real data.** Copy your workbook to
`data/HPRTC_Run-5.xlsx` (same sheet names as the original file), then:

```bash
streamlit run app.py
```

**Option B — try it immediately with synthetic sample data:**

```bash
python generate_sample_data.py   # writes data/HPRTC_Run-5.xlsx
streamlit run app.py
```

The sample data is randomly generated but physically consistent (it obeys
a real Arrhenius law, and simulates a thermal front sweeping through the
thermocouples over time), so every page — including the kinetics fit — has
something meaningful to show.

## Adapting the parsers to your real workbook

The sheets in the original export are messy (title rows, headers that don't
start at row 0, extra summary rows). Each `clean_*` function in
`utils/data_loader.py` locates its header row by matching a specific string
(e.g. `"Components"`, `"T Avg"`, `"Date"` + `"Time"`). If your sheet names or
header wording differ, adjust the matching strings there — that's the only
file you should need to touch to point this at a different export.

`load_hprtc_data()` tries every sheet independently and skips (rather than
crashes on) any sheet that fails to parse; check the "⚠️ sheets failed to
parse" expander in the app sidebar to see what to fix.

## Front velocity

`Temperature Profiles → calculate_front_velocity()` can compute a real
mm/h front velocity, but it needs each thermocouple's axial position. Fill
in the `default_positions` dict near the top of the "Temperature Profiles"
page in `app.py`:

```python
default_positions = {
    "TC 1 - Internal 1": 50,   # mm from injection end
    "TC 2 - Internal 2": 100,
    ...
}
```

Without positions, the page still shows arrival times and max/final
temperatures per thermocouple — just no velocity column.

## Notes

- **Mass Balance** page is a placeholder — add a `clean_mass_balance()`
  function to `utils/data_loader.py` (same pattern as the others) once you
  know which sheet holds it, then wire it into the page in `app.py`.
- Click **🔄 Reload data** in the sidebar any time you update the Excel file
  on disk — data is cached for speed and won't pick up changes otherwise.
