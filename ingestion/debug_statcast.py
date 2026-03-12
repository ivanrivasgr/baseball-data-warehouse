import duckdb
import os

BASE_DIR = os.path.abspath('.')
parquet = os.path.join(BASE_DIR, 'data', 'bronze', 'raw_statcast_2024.parquet').replace('\\', '/')
print('Path:', parquet)
print('File exists:', os.path.exists(parquet))

conn = duckdb.connect()

count = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{parquet}')").fetchone()
print('Total rows in parquet:', count)

count2 = conn.execute(f"""
    SELECT COUNT(*) FROM read_parquet('{parquet}')
    WHERE events IS NOT NULL AND launch_speed IS NOT NULL
""").fetchone()
print('Rows after filter:', count2)

sample = conn.execute(f"""
    SELECT batter, player_name, launch_speed, events
    FROM read_parquet('{parquet}')
    LIMIT 3
""").df()
print(sample)