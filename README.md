# Retail sales analytics (portfolio project)

End-to-end **data analyst** style project: synthetic B2C orders, **SQL analytics** (DuckDB), **Python** pipeline, **matplotlib** charts, optional **Streamlit** UI. Suitable to link from a CV or GitHub profile.

## Business question

How do **GMV**, **category mix**, **country AOV**, and **signup-based cohort retention** evolve for a multi-country online shop?

## What is inside

| Path | Description |
|------|-------------|
| `data/*.csv` | Small **demo** dataset (runs out of the box). Replace by running `scripts/generate_data.py` for ~1.2k customers / ~6 months. |
| `sql/*.sql` | Analytical queries (monthly GMV, category, country AOV, top products, cohort retention). |
| `src/run_pipeline.py` | Loads CSVs into DuckDB, runs every `.sql`, writes `outputs/*.csv` and `reports/*.png`. |
| `streamlit_app.py` | Lightweight viewer for tables and figures. |

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
python src/run_pipeline.py      # uses data/ CSVs
streamlit run streamlit_app.py
```

Regenerate a larger synthetic dataset (deterministic `seed=42`):

```bash
python scripts/generate_data.py
python src/run_pipeline.py
```

## Metrics (definitions)

- **GMV** — sum of `(quantity - quantity_returned) * unit_price_paid` for lines tied to orders in status `completed` or `returned` (partial returns supported). `cancelled` orders are excluded.
- **AOV** — GMV divided by distinct order count in the slice.
- **Cohort month** — calendar month of `signup_date`; **retention** — share of cohort customers with at least one qualifying order in month `signup + offset` (offsets 0–3).

## Tech stack

Python · DuckDB · Pandas · Matplotlib · Streamlit · Git

## Resume bullets (English)

- Built an end-to-end **retail analytics** portfolio: **SQL** metrics on orders, returns, and customer signup **cohorts**, executed with **DuckDB**, exported artifacts for reporting.
- Delivered **GMV / AOV / category mix** analyses and **matplotlib** charts, plus a **Streamlit** explorer for stakeholders.
- Added **reproducible synthetic data generation** (seeded) and a **GitHub Actions** workflow that regenerates data and runs the full pipeline on every push.

## License

MIT — use freely in a portfolio; synthetic data only.
