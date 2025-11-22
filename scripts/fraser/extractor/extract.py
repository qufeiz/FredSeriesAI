#!/usr/bin/env python3
"""TXT -> JSON extractor for FOMC meetings."""

from __future__ import annotations

import json
import os
from pathlib import Path

try:
    import openai  # type: ignore
except ImportError:  # pragma: no cover
    openai = None

BASE_DIR = Path(__file__).parent
MEETINGS_DIR = BASE_DIR / "meetings"
PROMPT_TEMPLATE = (BASE_DIR / "prompt.txt").read_text()
MODEL = os.getenv("EXTRACT_MODEL", "gpt-4.1-mini")
API_KEY = os.getenv("OPENAI_API_KEY")


def extract_json_from_text(raw_text: str) -> dict:
    if openai is None:
        raise RuntimeError("Please install openai (pip install openai).")
    if not API_KEY:
        raise RuntimeError("Set OPENAI_API_KEY to call the model.")

    prompt = PROMPT_TEMPLATE.replace("{{TEXT_HERE}}", raw_text)

    completion = openai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You output ONLY strict JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    content = completion.choices[0].message.content
    if not content:
        raise ValueError("Empty response from model.")
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned invalid JSON:\n{content}") from exc


def main() -> None:
    if not MEETINGS_DIR.exists():
        raise RuntimeError(f"Missing meetings directory: {MEETINGS_DIR}")

    txt_files = sorted(MEETINGS_DIR.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {MEETINGS_DIR}")
        return

    for txt_path in txt_files:
        raw_text = txt_path.read_text()
        data = extract_json_from_text(raw_text)

        json_path = txt_path.with_suffix(".json")
        json_path.write_text(json.dumps(data, indent=2))
        print(f"Extracted {json_path.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    main()
