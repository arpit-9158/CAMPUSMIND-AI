from backend.app.config import get_settings
from datetime import date, datetime, timedelta

from backend.app.data import load_timetable


def check_timetable(day: str | None = None, subject: str | None = None, semester: str | None = None, section: str | None = None, upcoming: bool = False) -> dict:
    rows = load_timetable(get_settings().path(get_settings().timetable_json_path))
    matches = [r for r in rows if (not day or r["day"].casefold() == day.casefold()) and (not subject or subject.casefold() in r["subject"].casefold()) and (not semester or str(r["semester"]) == str(semester)) and (not section or str(r["section"]).casefold() == section.casefold())]
    next_occurrence = None
    if upcoming and matches:
        now = datetime.now()
        weekdays = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}
        candidates = []
        for record in matches:
            offset = (weekdays[record["day"]] - now.weekday()) % 7
            occurrence = date.today() + timedelta(days=offset)
            if offset == 0 and datetime.strptime(record["start_time"], "%H:%M").time() <= now.time():
                occurrence += timedelta(days=7)
            candidates.append((occurrence.isoformat(), record["start_time"], record))
        occurrence_date, _, record = min(candidates, key=lambda item: (item[0], item[1]))
        matches = [record]
        next_occurrence = occurrence_date
    return {"found": bool(matches), "records": matches, "next_occurrence": next_occurrence, "message": "" if matches else "No matching sample timetable record was found."}
