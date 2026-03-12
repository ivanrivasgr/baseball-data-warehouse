# ⚾ MLB Baseball Data Warehouse

Multi-season analytics platform built on Bronze/Silver/Gold architecture using real MLB data.

## Stack
- **pybaseball** — MLB data ingestion (FanGraphs, Statcast)
- **DuckDB** — In-process analytical warehouse
- **Bronze/Silver/Gold** — Medallion architecture
- **Streamlit** — Interactive dashboard
- **Plotly** — Visualizations

## Architecture
```
pybaseball → Bronze (Parquet) → Silver (DuckDB views) → Gold (DuckDB tables) → Streamlit
```

## Data
- Batting & Pitching stats: 2022–2024 (FanGraphs via pybaseball)
- Statcast: 2024 season (Baseball Savant via pybaseball)
- 1,615 batter seasons · 1,420 pitcher seasons · 562 Statcast players

## Setup
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python ingestion/ingest.py
python ingestion/transform.py
streamlit run dashboard/app.py
```

## Live Demo
