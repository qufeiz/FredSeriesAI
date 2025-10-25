import json
import psycopg2

# 1. Load your local JSON file
with open("output/title_677_items.json", "r") as f:
    data = json.load(f)

# 2. Connect to your AWS PostgreSQL
conn = psycopg2.connect(
    host="fomc-db.c6voia0autyx.us-east-1.rds.amazonaws.com",
    user="postgres",
    password="Darky5657#",
    dbname="fomc"
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