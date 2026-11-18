import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

FAQ_COLUMNS = ["id", "category", "question", "answer", "source", "last_updated"]


def clean_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def load_faq_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"FAQ CSV not found: {path}")
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = sorted(set(FAQ_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"FAQ CSV is missing required columns: {', '.join(missing)}")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in frame[FAQ_COLUMNS].to_dict(orient="records"):
        item = {key: clean_text(value) for key, value in raw.items()}
        if not all(item.values()):
            raise ValueError(f"FAQ row has empty required fields: {item.get('id', '(unknown id)')}")
        if item["id"] in seen:
            raise ValueError(f"Duplicate FAQ id: {item['id']}")
        date.fromisoformat(item["last_updated"])
        seen.add(item["id"])
        rows.append(item)
    if not rows:
        raise ValueError("FAQ CSV contains no records")
    return rows


def load_json_records(path: Path, key: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Data JSON not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON in {path.name}: {exc.msg} at line {exc.lineno}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get(key), list):
        raise ValueError(f"{path.name} must contain a top-level '{key}' array")
    records = payload[key]
    if any(not isinstance(record, dict) for record in records):
        raise ValueError(f"Every item in {key} must be a JSON object")
    return records


def load_timetable(path: Path) -> list[dict[str, Any]]:
    records = load_json_records(path, "classes")
    required = {"day", "subject", "faculty", "start_time", "end_time", "room", "classroom", "section", "semester"}
    for item in records:
        missing = required - item.keys()
        if missing:
            raise ValueError(f"Timetable record missing fields: {', '.join(sorted(missing))}")
        if item.get("sample_data") is not True:
            raise ValueError("Timetable records must be explicitly marked sample_data=true")
    return records


def load_calendar(path: Path) -> list[dict[str, Any]]:
    records = load_json_records(path, "events")
    required = {"event_name", "event_date", "event_type", "description", "semester", "sample_data"}
    for item in records:
        missing = required - item.keys()
        if missing:
            raise ValueError(f"Calendar record missing fields: {', '.join(sorted(missing))}")
        date.fromisoformat(str(item["event_date"]))
        if item["sample_data"] is not True:
            raise ValueError("Calendar records must be explicitly marked sample_data=true")
    return records
