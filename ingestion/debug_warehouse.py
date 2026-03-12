import duckdb
import os

DB_PATH = os.path.join(os.path.abspath('.'), 'data', 'warehouse.duckdb')
parquet_abs = os.path.join(os.path.abspath('.'), 'data', 'bronze', 'raw_statcast_2024.parquet').replace('\\', '/')

conn = duckdb.connect(DB_PATH)

# Test grupos antes del HAVING
result2 = conn.execute(f"""
    SELECT COUNT(*) FROM (
        SELECT CAST(batter AS VARCHAR) AS batter_id, player_name, COUNT(*) as n
        FROM read_parquet('{parquet_abs}')
        WHERE events IS NOT NULL AND launch_speed IS NOT NULL
        GROUP BY CAST(batter AS VARCHAR), player_name
    )
""").fetchone()
print('Groups before HAVING:', result2)

# Nulls en player_name
nulls = conn.execute(f"""
    SELECT COUNT(*) FROM read_parquet('{parquet_abs}')
    WHERE player_name IS NULL
""").fetchone()
print('Rows with null player_name:', nulls)

# Top 5 grupos por conteo
sample = conn.execute(f"""
    SELECT CAST(batter AS VARCHAR) as batter_id, player_name, COUNT(*) as n
    FROM read_parquet('{parquet_abs}')
    GROUP BY CAST(batter AS VARCHAR), player_name
    ORDER BY n DESC
    LIMIT 5
""").df()
print(sample)

conn.close()