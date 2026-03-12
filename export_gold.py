import duckdb
import os

os.makedirs("data/gold", exist_ok=True)
conn = duckdb.connect("data/warehouse.duckdb", read_only=True)

conn.execute("COPY gold_player_season TO 'data/gold/batting.parquet' (FORMAT PARQUET)")
conn.execute("COPY gold_pitcher_performance TO 'data/gold/pitching.parquet' (FORMAT PARQUET)")
conn.execute("COPY gold_statcast_contact TO 'data/gold/statcast.parquet' (FORMAT PARQUET)")
conn.execute("COPY gold_team_offense TO 'data/gold/teams.parquet' (FORMAT PARQUET)")

conn.close()
print("Done! Files in data/gold/")

for f in os.listdir("data/gold"):
    size = os.path.getsize(f"data/gold/{f}") / 1024
    print(f"  {f}: {size:.1f} KB")