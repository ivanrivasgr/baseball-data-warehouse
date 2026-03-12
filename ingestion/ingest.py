import os
import pandas as pd
import pybaseball as pb

# ── CONFIG ─────────────────────────────────────────────────────────────────
BRONZE_DIR  = "data/bronze"
START_YEAR  = 2022
END_YEAR    = 2024

pb.cache.enable()

def save_parquet(df: pd.DataFrame, filename: str):
    os.makedirs(BRONZE_DIR, exist_ok=True)
    path = os.path.join(BRONZE_DIR, filename)
    df.to_parquet(path, index=False)
    print(f"  Saved {len(df):,} rows -> {path}")

def ingest_batting():
    print("Ingesting batting stats...")
    frames = []
    for year in range(START_YEAR, END_YEAR + 1):
        df = pb.batting_stats(year, qual=50)
        df["season"] = year
        frames.append(df)
    save_parquet(pd.concat(frames, ignore_index=True), "raw_batting.parquet")

def ingest_pitching():
    print("Ingesting pitching stats...")
    frames = []
    for year in range(START_YEAR, END_YEAR + 1):
        df = pb.pitching_stats(year, qual=30)
        df["season"] = year
        frames.append(df)
    save_parquet(pd.concat(frames, ignore_index=True), "raw_pitching.parquet")

def ingest_fielding():
    print("Ingesting fielding stats...")
    frames = []
    for year in range(START_YEAR, END_YEAR + 1):
        df = pb.fielding_stats(year, qual=50)
        df["season"] = year
        frames.append(df)
    save_parquet(pd.concat(frames, ignore_index=True), "raw_fielding.parquet")

def ingest_statcast_lightweight():
    """
    Solo batted balls de 2024 — deployable en Streamlit Cloud.
    El dashboard jalará esto en vivo desde pybaseball.
    Localmente lo guardamos para desarrollo rápido.
    """
    print("Ingesting Statcast 2024 (batted balls only)...")
    df = pb.statcast(
        start_dt="2024-04-01",
        end_dt="2024-10-01"
    )
    # Solo eventos con contacto real
    df = df[df["events"].notna()]
    df = df[df["launch_speed"].notna()]

    # Solo columnas que usamos — reduce peso drásticamente
    cols = [
        "game_date", "batter", "pitcher", "player_name",
        "pitch_type", "release_speed", "release_spin_rate",
        "launch_speed", "launch_angle", "hit_distance_sc",
        "events", "description", "bb_type",
        "estimated_ba_using_speedangle",
        "estimated_woba_using_speedangle",
        "home_team", "away_team", "inning"
    ]
    cols_available = [c for c in cols if c in df.columns]
    df = df[cols_available]
    df["season"] = 2024

    save_parquet(df, "raw_statcast_2024.parquet")

if __name__ == "__main__":
    print("Starting MLB data ingestion (deploy-ready version)")
    print(f"Batting/Pitching/Fielding: {START_YEAR}-{END_YEAR}")
    print("Statcast: 2024 batted balls only\n")

    ingest_batting()
    ingest_pitching()
    ingest_fielding()
    ingest_statcast_lightweight()

    print("\nIngestion complete.")
    print("Files in data/bronze/ ready for dbt models.")