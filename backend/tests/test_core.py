import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.agents.graph import _choose_tools
from backend.app.config import get_settings
from backend.app.data import load_calendar, load_faq_csv, load_timetable
from backend.app.main import app
from backend.app.tools.calendar_tool import check_academic_calendar
from backend.app.tools.email_tool import generate_email_draft
from backend.app.tools.timetable_tool import check_timetable

ROOT = Path(__file__).resolve().parents[2]
client = TestClient(app)


def test_faq_loads_at_least_35_valid_rows():
    rows = load_faq_csv(ROOT / "backend/data/faq.csv")
    assert len(rows) >= 35
    assert all(row["question"] and row["answer"] and row["source"] for row in rows)


def test_faq_policy_is_synthetic_and_attendance_is_present():
    row = next(r for r in load_faq_csv(ROOT / "backend/data/faq.csv") if r["id"] == "faq-001")
    assert "75 percent" in row["answer"]
    assert "Sample" in row["source"]


def test_faq_schema_rejects_missing_column(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("id,question\n1,question\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required columns"):
        load_faq_csv(path)


def test_faq_schema_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("id,category,question,answer,source,last_updated\n1,c,q,a,s,2026-01-01\n1,c,q2,a2,s,2026-01-01\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate FAQ id"):
        load_faq_csv(path)


def test_faq_schema_rejects_invalid_date(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("id,category,question,answer,source,last_updated\n1,c,q,a,s,invalid\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_faq_csv(path)


def test_timetable_json_loads_and_is_sample_marked():
    rows = load_timetable(ROOT / "backend/data/timetable.json")
    assert len(rows) >= 10
    assert all(r["sample_data"] for r in rows)


def test_calendar_json_loads_with_valid_dates():
    rows = load_calendar(ROOT / "backend/data/academic_calendar.json")
    assert len(rows) >= 8
    assert all(r["sample_data"] for r in rows)


def test_malformed_json_is_reported(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{ nope", encoding="utf-8")
    from backend.app.data import load_json_records
    with pytest.raises(ValueError, match="Malformed JSON"):
        load_json_records(path, "classes")


def test_timetable_filters_actual_monday_dbms_record():
    found = check_timetable(day="Monday", subject="DBMS")
    assert found["found"]
    assert found["records"][0]["id"] == "class-001"
    assert found["records"][0]["start_time"] == "09:00"


def test_timetable_missing_subject_is_structured_no_result():
    result = check_timetable(day="Monday", subject="Quantum Astronomy")
    assert result["found"] is False
    assert result["records"] == []


def test_timetable_upcoming_resolves_next_recurring_dbms_slot():
    result = check_timetable(subject="DBMS", upcoming=True)
    assert result["found"]
    assert len(result["records"]) == 1
    assert result["next_occurrence"]


def test_calendar_filters_actual_upcoming_exam():
    result = check_academic_calendar(event_type="Examination", upcoming=True)
    assert result["found"]
    assert result["records"][0]["event_name"] == "Internal Assessment 2"


def test_email_tool_does_not_send():
    draft = generate_email_draft("Department Office", "Leave", "medical leave")
    assert draft["sent"] is False
    assert "not sent" in draft["label"].lower()


def test_route_attendance_plus_monday_dbms():
    tools = [p["name"] for p in _choose_tools("What is the attendance requirement and when is my DBMS class on Monday?")]
    assert tools == ["search_university_faq", "check_timetable"]


def test_route_exam_and_reappear_rules():
    tools = [p["name"] for p in _choose_tools("When is the next examination, and what are the reappear examination rules?")]
    assert tools == ["search_university_faq", "check_academic_calendar"]


def test_route_leave_contact_and_email_draft():
    tools = [p["name"] for p in _choose_tools("Who should I contact for a leave application and help me draft an email to them?")]
    assert tools == ["search_university_faq", "generate_email_draft"]


def test_route_ai_tuesday_and_calendar_weekday_filter():
    plan = _choose_tools("Find my AI class on Tuesday and tell me whether any academic event is scheduled that day.")
    assert [p["name"] for p in plan] == ["check_timetable", "check_academic_calendar"]
    assert plan[-1]["input"]["weekday"] == "Tuesday"


def test_route_three_source_attendance_class_exam():
    tools = [p["name"] for p in _choose_tools("Tell me the minimum attendance requirement, my next DBMS class, and the next examination date.")]
    assert tools == ["search_university_faq", "check_timetable", "check_academic_calendar"]


def test_api_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_data_endpoints_return_actual_dataset_counts():
    stats = client.get("/stats").json()
    timetable = client.get("/timetable").json()
    calendar = client.get("/calendar").json()
    assert stats["faq_records"] >= 35
    assert stats["faq_chunks"] >= 40
    assert timetable["count"] >= 10 and timetable["sample_data"] is True
    assert calendar["count"] >= 8 and calendar["sample_data"] is True


def test_api_rejects_empty_chat_question():
    assert client.post("/chat", json={"question": "  "}).status_code == 422


def test_api_timetable_filter_returns_json_records():
    response = client.get("/timetable", params={"day": "Monday", "subject": "DBMS"})
    assert response.status_code == 200
    assert response.json()["records"][0]["id"] == "class-001"


def test_api_calendar_invalid_date_has_structured_error():
    response = client.get("/calendar", params={"on_date": "not-a-date"})
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "invalid_date"


def test_api_faq_explorer_returns_real_records():
    response = client.get("/faqs", params={"category": "Attendance"})
    assert response.status_code == 200
    assert response.json()["count"] >= 3


def test_streaming_api_emits_real_observable_events_and_final_answer():
    response = client.post("/chat/stream", json={"question": "What is my personal attendance percentage?"})
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "event: agent_event" in response.text
    assert "query_received" in response.text
    assert "response_generating" in response.text
    assert "response_completed" in response.text
    assert "event: final_answer" in response.text
    final_line = next(line for line in response.text.splitlines() if line.startswith("data: ") and '"answer"' in line)
    import json
    session = json.loads(final_line[6:])["session_id"]
    detail = client.get(f"/agent/activity/{session}")
    assert detail.status_code == 200
    assert detail.json()["session_id"] == session
    assert detail.json()["execution_summary"]
