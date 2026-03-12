import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import os
import sys

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MLB Baseball Data Warehouse",
    page_icon="⚾",
    layout="wide"
)

# ── CONNECTION ────────────────────────────────────────────────────────────────
DB_PATH    = "data/warehouse.duckdb"
BRONZE_DIR = "data/bronze"

def build_warehouse():
    import pybaseball as pb
    pb.cache.enable()

    st.info("Downloading MLB data... this takes 3-5 minutes on first load.")

    progress = st.progress(0, text="Ingesting batting stats...")
    frames = []
    for i, year in enumerate([2022, 2023, 2024]):
        df = pb.batting_stats(year, qual=50)
        df["season"] = year
        frames.append(df)
        progress.progress((i+1)/12, text=f"Batting {year} done...")
    batting = pd.concat(frames, ignore_index=True)

    frames = []
    for i, year in enumerate([2022, 2023, 2024]):
        df = pb.pitching_stats(year, qual=30)
        df["season"] = year
        frames.append(df)
        progress.progress(3/12 + (i+1)/12, text=f"Pitching {year} done...")
    pitching = pd.concat(frames, ignore_index=True)

    progress.progress(7/12, text="Ingesting Statcast 2024 (largest dataset)...")
    statcast = pb.statcast(start_dt="2024-04-01", end_dt="2024-10-01")
    statcast = statcast[statcast["events"].notna() & statcast["launch_speed"].notna()]
    cols = ["game_date","batter","pitcher","player_name","pitch_type",
            "release_speed","release_spin_rate","launch_speed","launch_angle",
            "hit_distance_sc","events","description","bb_type",
            "estimated_ba_using_speedangle","estimated_woba_using_speedangle",
            "home_team","away_team","inning"]
    statcast = statcast[[c for c in cols if c in statcast.columns]]
    statcast["season"] = 2024

    progress.progress(9/12, text="Building warehouse...")
    conn = duckdb.connect(DB_PATH)

    conn.execute("""
        CREATE OR REPLACE TABLE gold_player_season AS
        SELECT
            CAST("IDfg" AS VARCHAR) AS player_id,
            "Name" AS player_name, "Team" AS team,
            CAST("season" AS INTEGER) AS season,
            CAST("G" AS INTEGER) AS games,
            CAST("PA" AS INTEGER) AS plate_appearances,
            CAST("HR" AS INTEGER) AS home_runs,
            CAST("RBI" AS INTEGER) AS rbi,
            CAST("SB" AS INTEGER) AS stolen_bases,
            ROUND(CAST("AVG" AS DOUBLE), 3) AS avg,
            ROUND(CAST("OBP" AS DOUBLE), 3) AS obp,
            ROUND(CAST("SLG" AS DOUBLE), 3) AS slg,
            ROUND(CAST("OPS" AS DOUBLE), 3) AS ops,
            ROUND(CAST("wOBA" AS DOUBLE), 3) AS woba,
            ROUND(CAST("WAR" AS DOUBLE), 2) AS war,
            RANK() OVER (PARTITION BY CAST("season" AS INTEGER) ORDER BY CAST("WAR" AS DOUBLE) DESC) AS war_rank
        FROM batting
        WHERE CAST("PA" AS INTEGER) >= 50
    """)

    conn.execute("""
        CREATE OR REPLACE TABLE gold_pitcher_performance AS
        SELECT
            CAST("IDfg" AS VARCHAR) AS player_id,
            "Name" AS player_name, "Team" AS team,
            CAST("season" AS INTEGER) AS season,
            CAST("G" AS INTEGER) AS games,
            CAST("GS" AS INTEGER) AS games_started,
            ROUND(CAST("IP" AS DOUBLE), 1) AS innings_pitched,
            CAST("W" AS INTEGER) AS wins,
            CAST("L" AS INTEGER) AS losses,
            CAST("SO" AS INTEGER) AS strikeouts,
            ROUND(CAST("ERA" AS DOUBLE), 2) AS era,
            ROUND(CAST("WHIP" AS DOUBLE), 2) AS whip,
            ROUND(CAST("FIP" AS DOUBLE), 2) AS fip,
            ROUND(CAST("xFIP" AS DOUBLE), 2) AS xfip,
            ROUND(CAST("K/9" AS DOUBLE), 2) AS k_per_9,
            ROUND(CAST("BB/9" AS DOUBLE), 2) AS bb_per_9,
            ROUND(CAST("WAR" AS DOUBLE), 2) AS war,
            RANK() OVER (PARTITION BY CAST("season" AS INTEGER) ORDER BY CAST("WAR" AS DOUBLE) DESC) AS war_rank
        FROM pitching
        WHERE CAST("IP" AS DOUBLE) >= 20
    """)

    conn.execute("""
        CREATE OR REPLACE TABLE gold_statcast_contact AS
        SELECT
            CAST(batter AS VARCHAR) AS batter_id,
            FIRST(player_name) AS batter_name,
            COUNT(*) AS batted_balls,
            ROUND(AVG(CAST(launch_speed AS DOUBLE)), 1) AS avg_exit_velo,
            ROUND(AVG(CAST(launch_angle AS DOUBLE)), 1) AS avg_launch_angle,
            ROUND(AVG(CAST(estimated_ba_using_speedangle AS DOUBLE)), 3) AS avg_xba,
            ROUND(AVG(CAST(estimated_woba_using_speedangle AS DOUBLE)), 3) AS avg_xwoba,
            ROUND(100.0 * SUM(CASE WHEN CAST(launch_speed AS DOUBLE) >= 95 THEN 1 ELSE 0 END) / COUNT(*), 1) AS hard_hit_pct,
            ROUND(100.0 * SUM(CASE WHEN CAST(launch_speed AS DOUBLE) >= 98 AND CAST(launch_angle AS DOUBLE) BETWEEN 26 AND 30 THEN 1 ELSE 0 END) / COUNT(*), 1) AS barrel_pct
        FROM statcast
        GROUP BY CAST(batter AS VARCHAR)
        HAVING COUNT(*) >= 20
    """)

    conn.execute("""
        CREATE OR REPLACE TABLE gold_team_offense AS
        SELECT
            team, season,
            COUNT(DISTINCT player_id) AS players,
            ROUND(AVG(avg), 3) AS team_avg,
            ROUND(AVG(ops), 3) AS team_ops,
            ROUND(AVG(woba), 3) AS team_woba,
            SUM(home_runs) AS total_hr,
            SUM(rbi) AS total_rbi,
            ROUND(SUM(war), 1) AS total_war,
            RANK() OVER (PARTITION BY season ORDER BY SUM(war) DESC) AS war_rank
        FROM gold_player_season
        GROUP BY team, season
    """)

    conn.close()
    progress.progress(1.0, text="Warehouse ready!")
    st.success("✅ Data loaded! Please wait...")
    import time
    time.sleep(2)
    st.rerun()

@st.cache_resource
def get_conn():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(DB_PATH):
        build_warehouse()
        st.stop()
    return duckdb.connect(DB_PATH, read_only=True)

@st.cache_data
def query(_conn, sql):
    return _conn.execute(sql).df()

conn = get_conn()

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/a/a6/Major_League_Baseball_logo.svg/200px-Major_League_Baseball_logo.svg.png", width=120)
st.sidebar.title("MLB Data Warehouse")
st.sidebar.markdown("Bronze · Silver · Gold Architecture")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate",
    ["Overview", "Batting", "Pitching", "Statcast 2024", "Team Rankings"]
)

seasons = query(conn, "SELECT DISTINCT season FROM gold_player_season ORDER BY season DESC")["season"].tolist()
selected_season = st.sidebar.selectbox("Season", seasons)

# ── OVERVIEW ──────────────────────────────────────────────────────────────────
if page == "Overview":
    st.title("⚾ MLB Baseball Data Warehouse")
    st.markdown("Multi-season analytics platform built on **Bronze/Silver/Gold** architecture using **DuckDB**, **pybaseball**, and **Streamlit**.")

    col1, col2, col3, col4 = st.columns(4)

    batting_count = query(conn, "SELECT COUNT(*) as n FROM gold_player_season")["n"][0]
    pitching_count = query(conn, "SELECT COUNT(*) as n FROM gold_pitcher_performance")["n"][0]
    statcast_count = query(conn, "SELECT COUNT(*) as n FROM gold_statcast_contact")["n"][0]
    team_count = query(conn, "SELECT COUNT(DISTINCT team) as n FROM gold_team_offense")["n"][0]

    col1.metric("Batter Seasons", f"{batting_count:,}")
    col2.metric("Pitcher Seasons", f"{pitching_count:,}")
    col3.metric("Statcast Players", f"{statcast_count:,}")
    col4.metric("Teams", f"{team_count:,}")

    st.markdown("---")
    st.subheader("Pipeline Architecture")
    col1, col2, col3 = st.columns(3)
    col1.success("🟤 Bronze Layer\n\nRaw Parquet files from pybaseball\n\nBatting · Pitching · Fielding · Statcast")
    col2.info("⚪ Silver Layer\n\nCleaned & typed DuckDB views\n\nStandardized schemas, null handling")
    col3.warning("🟡 Gold Layer\n\nAnalytics-ready tables\n\nMetrics, rankings, aggregations")

    st.markdown("---")
    st.subheader(f"Top 10 Batters by WAR — {selected_season}")
    top_war = query(conn, f"""
        SELECT player_name, team, war, ops, home_runs, avg
        FROM gold_player_season
        WHERE season = {selected_season}
        ORDER BY war DESC LIMIT 10
    """)
    fig = px.bar(top_war, x="war", y="player_name", orientation="h",
                 color="war", color_continuous_scale="Blues",
                 labels={"war": "WAR", "player_name": "Player"})
    fig.update_layout(yaxis=dict(autorange="reversed"), height=400)
    st.plotly_chart(fig, use_container_width=True)

# ── BATTING ───────────────────────────────────────────────────────────────────
elif page == "Batting":
    st.title(f"⚾ Batting — {selected_season}")

    df = query(conn, f"""
        SELECT player_name, team, games, plate_appearances,
               home_runs, rbi, stolen_bases, avg, obp, slg, ops, woba, war
        FROM gold_player_season
        WHERE season = {selected_season}
        ORDER BY war DESC
    """)

    col1, col2, col3 = st.columns(3)
    col1.metric("HR Leader", f"{df.iloc[df['home_runs'].idxmax()]['player_name']}", f"{df['home_runs'].max()} HR")
    col2.metric("AVG Leader", f"{df.iloc[df['avg'].idxmax()]['player_name']}", f"{df['avg'].max():.3f}")
    col3.metric("WAR Leader", f"{df.iloc[df['war'].idxmax()]['player_name']}", f"{df['war'].max():.1f} WAR")

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("OPS vs WAR")
        fig = px.scatter(df, x="ops", y="war", hover_name="player_name",
                         color="home_runs", size="plate_appearances",
                         color_continuous_scale="Reds",
                         labels={"ops": "OPS", "war": "WAR", "home_runs": "HR"})
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("wOBA Distribution")
        fig = px.histogram(df, x="woba", nbins=30, color_discrete_sequence=["#1f77b4"])
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Full Batting Table")
    search = st.text_input("Search player")
    if search:
        df = df[df["player_name"].str.contains(search, case=False)]
    st.dataframe(df, use_container_width=True, hide_index=True)

# ── PITCHING ──────────────────────────────────────────────────────────────────
elif page == "Pitching":
    st.title(f"⚾ Pitching — {selected_season}")

    df = query(conn, f"""
        SELECT player_name, team, games, games_started, innings_pitched,
               wins, losses, strikeouts, era, whip, fip, xfip, k_per_9, bb_per_9, war
        FROM gold_pitcher_performance
        WHERE season = {selected_season}
        ORDER BY war DESC
    """)

    col1, col2, col3 = st.columns(3)
    col1.metric("ERA Leader", f"{df.iloc[df['era'].idxmin()]['player_name']}", f"{df['era'].min():.2f} ERA")
    col2.metric("K Leader", f"{df.iloc[df['strikeouts'].idxmax()]['player_name']}", f"{df['strikeouts'].max()} K")
    col3.metric("WAR Leader", f"{df.iloc[df['war'].idxmax()]['player_name']}", f"{df['war'].max():.1f} WAR")

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("ERA vs FIP")
        fig = px.scatter(df, x="era", y="fip", hover_name="player_name",
                         color="war", size="innings_pitched",
                         color_continuous_scale="RdYlGn_r",
                         labels={"era": "ERA", "fip": "FIP", "war": "WAR"})
        fig.add_shape(type="line", x0=df["era"].min(), y0=df["era"].min(),
                      x1=df["era"].max(), y1=df["era"].max(),
                      line=dict(dash="dash", color="gray"))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("K/9 vs BB/9")
        fig = px.scatter(df, x="bb_per_9", y="k_per_9", hover_name="player_name",
                         color="era", color_continuous_scale="RdYlGn_r",
                         labels={"bb_per_9": "BB/9", "k_per_9": "K/9", "era": "ERA"})
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Full Pitching Table")
    search = st.text_input("Search pitcher")
    if search:
        df = df[df["player_name"].str.contains(search, case=False)]
    st.dataframe(df, use_container_width=True, hide_index=True)

# ── STATCAST ──────────────────────────────────────────────────────────────────
elif page == "Statcast 2024":
    st.title("📡 Statcast Quality of Contact — 2024")
    st.markdown("Exit velocity, launch angle, xBA, xwOBA and barrel rate for all qualified hitters.")

    df = query(conn, """
        SELECT batter_name, batted_balls, avg_exit_velo,
               avg_launch_angle, avg_xba, avg_xwoba,
               hard_hit_pct, barrel_pct
        FROM gold_statcast_contact
        ORDER BY avg_exit_velo DESC
    """)

    col1, col2, col3 = st.columns(3)
    if len(df) > 0:
        col1.metric("Hardest Hitter", df.iloc[0]["batter_name"], f"{df.iloc[0]['avg_exit_velo']} mph")
        col2.metric("Highest xwOBA", df.loc[df["avg_xwoba"].idxmax(), "batter_name"], f"{df['avg_xwoba'].max():.3f}")
        col3.metric("Barrel% Leader", df.loc[df["barrel_pct"].idxmax(), "batter_name"], f"{df['barrel_pct'].max():.1f}%")
    else:
        st.warning("No Statcast data available.")

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Exit Velocity vs Barrel%")
        fig = px.scatter(df, x="avg_exit_velo", y="barrel_pct",
                         hover_name="batter_name", color="avg_xwoba",
                         color_continuous_scale="Viridis",
                         labels={"avg_exit_velo": "Avg Exit Velo (mph)",
                                 "barrel_pct": "Barrel %",
                                 "avg_xwoba": "xwOBA"})
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Hard Hit % Leaders")
        top20 = df.nlargest(20, "hard_hit_pct")
        fig = px.bar(top20, x="hard_hit_pct", y="batter_name",
                     orientation="h", color="hard_hit_pct",
                     color_continuous_scale="Oranges",
                     labels={"hard_hit_pct": "Hard Hit %", "batter_name": "Player"})
        fig.update_layout(yaxis=dict(autorange="reversed"), height=500)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Full Statcast Table")
    search = st.text_input("Search player")
    if search:
        df = df[df["batter_name"].str.contains(search, case=False, na=False)]
    st.dataframe(df, use_container_width=True, hide_index=True)

# ── TEAM RANKINGS ─────────────────────────────────────────────────────────────
elif page == "Team Rankings":
    st.title(f"🏆 Team Offensive Rankings — {selected_season}")

    df = query(conn, f"""
        SELECT team, players, team_avg, team_ops, team_woba,
               total_hr, total_rbi, total_war, war_rank
        FROM gold_team_offense
        WHERE season = {selected_season}
        ORDER BY war_rank
    """)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Total WAR by Team")
        fig = px.bar(df.head(15), x="total_war", y="team",
                     orientation="h", color="total_war",
                     color_continuous_scale="Blues",
                     labels={"total_war": "Total WAR", "team": "Team"})
        fig.update_layout(yaxis=dict(autorange="reversed"), height=500)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Team OPS vs wOBA")
        fig = px.scatter(df, x="team_ops", y="team_woba",
                         hover_name="team", color="total_hr",
                         size=df["total_war"].clip(lower=0),
                         color_continuous_scale="Reds",
                         labels={"team_ops": "Team OPS",
                                 "team_woba": "Team wOBA",
                                 "total_hr": "Total HR"})
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Full Team Rankings Table")
    st.dataframe(df, use_container_width=True, hide_index=True)