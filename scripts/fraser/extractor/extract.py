#!/usr/bin/env python3
# Minimal TXT -> JSON extractor for FOMC meetings (POC-friendly).

import json
import os
from pathlib import Path

import openai  # pip install openai>=1.0.0
from dotenv import load_dotenv  # pip install python-dotenv

load_dotenv()

BASE = Path(__file__).parent
PROMPT = (BASE / "prompt.txt").read_text()
MEETINGS_DIR = BASE / "meetings"
MODEL = os.getenv("EXTRACT_MODEL", "gpt-5-mini")
API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    raise SystemExit("Set OPENAI_API_KEY before running.")

client = openai.OpenAI(api_key=API_KEY)

txt_files = sorted(MEETINGS_DIR.glob("*.txt"))
if not txt_files:
    raise SystemExit(f"No .txt files in {MEETINGS_DIR}")

for txt in txt_files:
    print(f"Extracting {txt.name} ...", end="", flush=True)
    raw_text = txt.read_text()
    prompt = PROMPT.replace("{{TEXT_HERE}}", raw_text)

    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You output ONLY strict JSON."},
            {"role": "user", "content": prompt},
        ],
        # omit temperature to satisfy models that only allow defaults
    )
    content = completion.choices[0].message.content
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise SystemExit(f"\nModel returned invalid JSON for {txt.name}:\n{content}")

    out_path = txt.with_suffix(".json")
    out_path.write_text(json.dumps(data, indent=2))
    print(f" -> {out_path.name}")
