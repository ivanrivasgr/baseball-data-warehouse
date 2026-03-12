import duckdb
import os

# ── CONFIG ────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH    = os.path.join(BASE_DIR, "data", "warehouse.duckdb")
BRONZE_DIR = os.path.join(BASE_DIR, "data", "bronze").replace("\\", "/")

def get_conn():
    os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
    return duckdb.connect(DB_PATH)

def create_silver(conn):
    print("Building Silver layer...")
    print(f"  Reading from: {BRONZE_DIR}")

    conn.execute(f"""
        CREATE OR REPLACE VIEW silver_batting AS
        SELECT
            CAST("IDfg" AS VARCHAR)          AS player_id,
            "Name"                            AS player_name,
            "Team"                            AS team,
            CAST("season" AS INTEGER)         AS season,
            CAST("G"   AS INTEGER)            AS games,
            CAST("AB"  AS INTEGER)            AS at_bats,
            CAST("PA"  AS INTEGER)            AS plate_appearances,
            CAST("H"   AS INTEGER)            AS hits,
            CAST("HR"  AS INTEGER)            AS home_runs,
            CAST("R"   AS INTEGER)            AS runs,
            CAST("RBI" AS INTEGER)            AS rbi,
            CAST("SB"  AS INTEGER)            AS stolen_bases,
            CAST("BB"  AS INTEGER)            AS walks,
            CAST("SO"  AS INTEGER)            AS strikeouts,
            ROUND(CAST("AVG"  AS DOUBLE), 3)  AS avg,
            ROUND(CAST("OBP"  AS DOUBLE), 3)  AS obp,
            ROUND(CAST("SLG"  AS DOUBLE), 3)  AS slg,
            ROUND(CAST("OPS"  AS DOUBLE), 3)  AS ops,
            ROUND(CAST("wOBA" AS DOUBLE), 3)  AS woba,
            ROUND(CAST("WAR"  AS DOUBLE), 2)  AS war
        FROM read_parquet('{BRONZE_DIR}/raw_batting.parquet')
        WHERE CAST("PA" AS INTEGER) >= 50
    """)
    print("  silver_batting OK")

    conn.execute(f"""
        CREATE OR REPLACE VIEW silver_pitching AS
        SELECT
            CAST("IDfg" AS VARCHAR)           AS player_id,
            "Name"                             AS player_name,
            "Team"                             AS team,
            CAST("season" AS INTEGER)          AS season,
            CAST("G"  AS INTEGER)              AS games,
            CAST("GS" AS INTEGER)              AS games_started,
            ROUND(CAST("IP" AS DOUBLE), 1)     AS innings_pitched,
            CAST("W"  AS INTEGER)              AS wins,
            CAST("L"  AS INTEGER)              AS losses,
            CAST("SV" AS INTEGER)              AS saves,
            CAST("SO" AS INTEGER)              AS strikeouts,
            CAST("BB" AS INTEGER)              AS walks,
            CAST("HR" AS INTEGER)              AS home_runs_allowed,
            ROUND(CAST("ERA"  AS DOUBLE), 2)   AS era,
            ROUND(CAST("WHIP" AS DOUBLE), 2)   AS whip,
            ROUND(CAST("FIP"  AS DOUBLE), 2)   AS fip,
            ROUND(CAST("xFIP" AS DOUBLE), 2)   AS xfip,
            ROUND(CAST("K/9"  AS DOUBLE), 2)   AS k_per_9,
            ROUND(CAST("BB/9" AS DOUBLE), 2)   AS bb_per_9,
            ROUND(CAST("WAR"  AS DOUBLE), 2)   AS war
        FROM read_parquet('{BRONZE_DIR}/raw_pitching.parquet')
        WHERE CAST("IP" AS DOUBLE) >= 20
    """)
    print("  silver_pitching OK")

    conn.execute(f"""
        CREATE OR REPLACE VIEW silver_statcast AS
        SELECT
            CAST(game_date AS DATE)                                           AS game_date,
            CAST(batter AS VARCHAR)                                           AS batter_id,
            player_name                                                       AS batter_name,
            pitch_type,
            ROUND(CAST(release_speed AS DOUBLE), 1)                          AS pitch_velocity,
            ROUND(CAST(launch_speed AS DOUBLE), 1)                           AS exit_velocity,
            ROUND(CAST(launch_angle AS DOUBLE), 1)                           AS launch_angle,
            ROUND(CAST(hit_distance_sc AS DOUBLE), 0)                        AS hit_distance,
            events                                                            AS event,
            bb_type                                                           AS batted_ball_type,
            ROUND(CAST(estimated_ba_using_speedangle AS DOUBLE), 3)          AS xba,
            ROUND(CAST(estimated_woba_using_speedangle AS DOUBLE), 3)        AS xwoba,
            CAST(season AS INTEGER)                                           AS season
        FROM read_parquet('{BRONZE_DIR}/raw_statcast_2024.parquet')
        WHERE events IS NOT NULL
          AND launch_speed IS NOT NULL
    """)
    print("  silver_statcast OK")

def create_gold(conn):
    print("Building Gold layer...")

    conn.execute("""
        CREATE OR REPLACE TABLE gold_player_season AS
        SELECT
            player_id,
            player_name,
            team,
            season,
            games,
            plate_appearances,
            home_runs,
            rbi,
            stolen_bases,
            avg,
            obp,
            slg,
            ops,
            woba,
            war,
            ROUND(ops + 0.0, 3) AS ops_plus_approx,
            RANK() OVER (PARTITION BY season ORDER BY war DESC) AS war_rank
        FROM silver_batting
    """)
    print("  gold_player_season OK")

    conn.execute("""
        CREATE OR REPLACE TABLE gold_pitcher_performance AS
        SELECT
            player_id,
            player_name,
            team,
            season,
            games,
            games_started,
            innings_pitched,
            wins,
            losses,
            strikeouts,
            era,
            whip,
            fip,
            xfip,
            k_per_9,
            bb_per_9,
            war,
            RANK() OVER (PARTITION BY season ORDER BY war DESC) AS war_rank
        FROM silver_pitching
    """)
    print("  gold_pitcher_performance OK")

    conn.execute(f"""
        CREATE OR REPLACE TABLE gold_statcast_contact AS
        WITH base AS (
            SELECT
                CAST(batter AS VARCHAR)                          AS batter_id,
                COUNT(*)                                         AS batted_balls,
                ROUND(AVG(CAST(launch_speed AS DOUBLE)), 1)     AS avg_exit_velo,
                ROUND(AVG(CAST(launch_angle AS DOUBLE)), 1)     AS avg_launch_angle,
                ROUND(AVG(CAST(estimated_ba_using_speedangle AS DOUBLE)), 3)   AS avg_xba,
                ROUND(AVG(CAST(estimated_woba_using_speedangle AS DOUBLE)), 3) AS avg_xwoba,
                ROUND(100.0 * SUM(CASE WHEN CAST(launch_speed AS DOUBLE) >= 95
                                       THEN 1 ELSE 0 END) / COUNT(*), 1)      AS hard_hit_pct,
                ROUND(100.0 * SUM(CASE WHEN CAST(launch_speed AS DOUBLE) >= 98
                                        AND CAST(launch_angle AS DOUBLE) BETWEEN 26 AND 30
                                   THEN 1 ELSE 0 END) / COUNT(*), 1)          AS barrel_pct
            FROM read_parquet('{BRONZE_DIR}/raw_statcast_2024.parquet')
            WHERE events IS NOT NULL
              AND launch_speed IS NOT NULL
            GROUP BY CAST(batter AS VARCHAR)
            HAVING COUNT(*) >= 20
        )
        SELECT
            b.batter_id,
            COALESCE(s.batter_name, b.batter_id) AS batter_name,
            b.batted_balls,
            b.avg_exit_velo,
            b.avg_launch_angle,
            b.avg_xba,
            b.avg_xwoba,
            b.hard_hit_pct,
            b.barrel_pct
        FROM base b
        LEFT JOIN (
            SELECT DISTINCT
                CAST(batter AS VARCHAR) AS batter_id,
                FIRST(player_name) AS batter_name
            FROM read_parquet('{BRONZE_DIR}/raw_statcast_2024.parquet')
            GROUP BY CAST(batter AS VARCHAR)
        ) s ON b.batter_id = s.batter_id
    """)
    print("  gold_statcast_contact OK")

    conn.execute("""
        CREATE OR REPLACE TABLE gold_team_offense AS
        SELECT
            team,
            season,
            COUNT(DISTINCT player_id)     AS players,
            ROUND(AVG(avg), 3)            AS team_avg,
            ROUND(AVG(ops), 3)            AS team_ops,
            ROUND(AVG(woba), 3)           AS team_woba,
            SUM(home_runs)                AS total_hr,
            SUM(rbi)                      AS total_rbi,
            ROUND(SUM(war), 1)            AS total_war,
            RANK() OVER (PARTITION BY season ORDER BY SUM(war) DESC) AS war_rank
        FROM silver_batting
        GROUP BY team, season
    """)
    print("  gold_team_offense OK")

if __name__ == "__main__":
    print("Starting transformation pipeline...")
    conn = get_conn()
    create_silver(conn)
    create_gold(conn)
    conn.close()
    print("\nTransformation complete.")
    print(f"DuckDB warehouse ready at {DB_PATH}")