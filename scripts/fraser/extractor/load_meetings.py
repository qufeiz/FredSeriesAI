#!/usr/bin/env python3
"""Load extracted meeting JSON files into Postgres."""

import json
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

BASE = Path(__file__).parent
MEETINGS_DIR = BASE / "meetings"

DB_HOST = os.getenv("PG_HOST")
DB_PORT = int(os.getenv("PG_PORT", "5432"))
DB_NAME = os.getenv("PG_NAME", "fomc")
DB_USER = os.getenv("PG_USER")
DB_PASS = os.getenv("PG_PASS")

if not all([DB_HOST, DB_USER, DB_PASS]):
    raise SystemExit("Set DB_HOST, DB_USER, DB_PASS (and optionally DB_NAME, DB_PORT) in env/.env.")

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASS,
)
cur = conn.cursor()

cur.execute(
    """
    CREATE TABLE IF NOT EXISTS fomc_meetings (
      meeting_id TEXT PRIMARY KEY,
      meeting_date DATE NOT NULL,
      target_range_low NUMERIC,
      target_range_high NUMERIC,
      ioer NUMERIC,
      on_rrp NUMERIC,
      repo_min_rate NUMERIC,
      primary_credit_rate NUMERIC,
      votes_for INTEGER,
      votes_against INTEGER
    );
    """
)

json_files = sorted(MEETINGS_DIR.glob("*.json"))
if not json_files:
    raise SystemExit(f"No .json files in {MEETINGS_DIR}")

for path in json_files:
    data = json.loads(path.read_text())
    cur.execute(
        """
        INSERT INTO fomc_meetings (
          meeting_id, meeting_date,
          target_range_low, target_range_high,
          ioer, on_rrp, repo_min_rate, primary_credit_rate,
          votes_for, votes_against
        )
        VALUES (
          %(meeting_id)s, %(meeting_date)s,
          %(target_range_low)s, %(target_range_high)s,
          %(ioer)s, %(on_rrp)s, %(repo_min_rate)s, %(primary_credit_rate)s,
          %(votes_for)s, %(votes_against)s
        )
        ON CONFLICT (meeting_id) DO UPDATE SET
          target_range_low = EXCLUDED.target_range_low,
          target_range_high = EXCLUDED.target_range_high,
          ioer = EXCLUDED.ioer,
          on_rrp = EXCLUDED.on_rrp,
          repo_min_rate = EXCLUDED.repo_min_rate,
          primary_credit_rate = EXCLUDED.primary_credit_rate,
          votes_for = EXCLUDED.votes_for,
          votes_against = EXCLUDED.votes_against;
        """,
        data,
    )
    print(f"Upserted {path.name}")

conn.commit()
cur.close()
conn.close()
print("Done.")
