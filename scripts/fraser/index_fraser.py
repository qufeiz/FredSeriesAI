import json
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

PG_HOST = os.getenv("PG_HOST")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_NAME = os.getenv("PG_NAME", "fomc")
PG_USER = os.getenv("PG_USER")
PG_PASS = os.getenv("PG_PASS")

if not all([PG_HOST, PG_USER, PG_PASS]):
    raise SystemExit("Set PG_HOST, PG_USER, PG_PASS (and optionally PG_NAME, PG_PORT) in env/.env.")

# 1. Load your local JSON file
with open("output/title_677_items.json", "r") as f:
    data = json.load(f)

# 2. Connect to Postgres
conn = psycopg2.connect(
    host=PG_HOST,
    port=PG_PORT,
    user=PG_USER,
    password=PG_PASS,
    dbname=PG_NAME,
)
cur = conn.cursor()

# 3. Loop and insert
for item in data["records"]:
    cur.execute("""
        INSERT INTO fomc_items (id, titleInfo, originInfo, location, recordInfo)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """, (
        item["recordInfo"]["recordIdentifier"][0],
        json.dumps(item["titleInfo"]),
        json.dumps(item.get("originInfo", {})),
        json.dumps(item.get("location", {})),
        json.dumps(item["recordInfo"])
    ))

conn.commit()
cur.close()
conn.close()

print("✅ All FOMC items inserted.")
