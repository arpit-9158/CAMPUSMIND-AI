from datetime import date

from backend.app.config import get_settings
from backend.app.data import load_calendar


def check_academic_calendar(on_date: str | None = None, event_type: str | None = None, upcoming: bool = False, weekday: str | None = None) -> dict:
    rows = load_calendar(get_settings().path(get_settings().calendar_json_path))
    target = date.fromisoformat(on_date) if on_date else None
    today = date.today()
    matches = [r for r in rows if (not target or r["event_date"] == target.isoformat()) and (not weekday or date.fromisoformat(r["event_date"]).strftime("%A").casefold() == weekday.casefold()) and (not event_type or event_type.casefold() in r["event_type"].casefold()) and (not upcoming or date.fromisoformat(r["event_date"]) >= today)]
    matches.sort(key=lambda r: r["event_date"])
    if upcoming and matches:
        next_date = matches[0]["event_date"]
        matches = [r for r in matches if r["event_date"] == next_date]
    return {"found": bool(matches), "records": matches, "message": "" if matches else "No matching sample academic-calendar event was found."}
