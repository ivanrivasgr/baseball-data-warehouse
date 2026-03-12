# Baseball Data Warehouse

A multi-season MLB analytics platform built on a Bronze/Silver/Gold medallion architecture. Ingests real data from FanGraphs and Baseball Savant, transforms it through DuckDB, and serves it via an interactive Streamlit dashboard.

**[Live Demo →](https://baseball-data-warehouse-rmcyuzode7nmgcvwdfnxgi.streamlit.app/)**

---

## What it does

Pulls batting, pitching, and Statcast data for the 2022–2024 MLB seasons, runs it through a lightweight data warehouse pipeline, and exposes five analytics views: season batting leaders, pitching performance, Statcast contact quality, and team offensive rankings.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        PIPELINE                             │
│                                                             │
│  pybaseball API                                             │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────┐    ┌──────────┐    ┌──────────────────────┐   │
│  │ BRONZE  │───▶│  SILVER  │───▶│        GOLD          │   │
│  │         │    │          │    │                      │   │
│  │ Raw     │    │ Cleaned  │    │ Pre-materialized     │   │
│  │ Parquet │    │ DuckDB   │    │ Parquet files        │   │
│  │ files   │    │ views    │    │ (committed to repo)  │   │
│  └─────────┘    └──────────┘    └──────────────────────┘   │
│                                          │                  │
└──────────────────────────────────────────┼──────────────────┘
                                           │
                                           ▼
                               ┌───────────────────────┐
                               │   Streamlit Dashboard  │
                               │                       │
                               │  DuckDB (in-memory)   │
                               │  reads Gold Parquet   │
                               │  → Plotly charts      │
                               └───────────────────────┘
```

### Gold tables

| Table | Description | Rows |
|---|---|---|
| `gold_player_season` | Batter seasons with WAR rank | ~1,600 |
| `gold_pitcher_performance` | Pitcher seasons with WAR rank | ~1,400 |
| `gold_statcast_contact` | Exit velo, barrel%, xwOBA per batter | ~560 |
| `gold_team_offense` | Team offensive aggregates by season | ~90 |

---

## Stack

- **Ingestion:** [pybaseball](https://github.com/jldbc/pybaseball) — FanGraphs batting/pitching stats + Baseball Savant Statcast
- **Warehouse:** DuckDB — SQL transformations and gold table materialization
- **Dashboard:** Streamlit + Plotly
- **Deploy:** Streamlit Community Cloud (free, permanent)

---

## Why these tools

**DuckDB over Postgres/Snowflake:** This is an analytical workload on static data — no concurrent writes, no row-level transactions. DuckDB runs entirely in-process, handles Parquet natively, and executes the same SQL you'd write in any warehouse. Zero infrastructure to manage.

**Pre-materialized Parquet over live downloads:** The pipeline and the dashboard are separate concerns. The Gold layer gets built once locally (or in CI), committed to the repo as small Parquet files (~160KB total), and the dashboard just reads them. This means the app starts in seconds instead of waiting 8 minutes for Statcast to download on every cold start. Same pattern used in production — a scheduled job refreshes the Gold layer, the serving layer only reads.

**pybaseball over paid APIs:** Free, covers FanGraphs and Baseball Savant, and the data quality is the same as what analysts use in the industry. Good enough for a portfolio project that demonstrates the pipeline, not the data sourcing.

---

## Run locally

**Requirements:** Python 3.10+

```bash
git clone https://github.com/ivanrivasgr/baseball-data-warehouse.git
cd baseball-data-warehouse
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Option A — use pre-built Gold data (fast, no downloads):**
```bash
streamlit run dashboard/app.py
```

**Option B — rebuild from scratch:**
```bash
# Ingest raw data from FanGraphs + Baseball Savant (~8 min)
python ingestion/ingest.py

# Transform into Gold tables
python ingestion/transform.py

# Re-export Gold Parquet files
python export_gold.py

streamlit run dashboard/app.py
```

---

## Project structure

```
baseball-data-warehouse/
├── dashboard/
│   └── app.py              # Streamlit app
├── ingestion/
│   ├── ingest.py           # Downloads raw data via pybaseball
│   └── transform.py        # Builds Gold tables in DuckDB
├── gold_data/              # Pre-materialized Gold Parquet files
│   ├── batting.parquet
│   ├── pitching.parquet
│   ├── statcast.parquet
│   └── teams.parquet
├── data/
│   └── bronze/             # Raw Parquet files (gitignored)
├── export_gold.py          # Exports DuckDB Gold tables → Parquet
├── requirements.txt
└── README.md
```

---

## Data sources

- **FanGraphs** via pybaseball — batting and pitching season stats (2022–2024)
- **Baseball Savant** via pybaseball — Statcast batted ball data (2024 season)

Stats include standard slash line, advanced metrics (wOBA, FIP, xFIP), Statcast contact quality (exit velocity, barrel rate, hard hit%), and WAR from FanGraphs.