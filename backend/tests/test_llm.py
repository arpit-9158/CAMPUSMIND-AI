from types import SimpleNamespace

from backend.app import llm


def test_answer_uses_verified_evidence_without_raw_path_citations(monkeypatch):
    class StubClient:
        def chat(self, **kwargs):
            return SimpleNamespace(message=SimpleNamespace(content="The examination date is not specified. However, the event is on November 23, 2026. [FAQ-001] [check_academic_calendar]"))

    monkeypatch.setattr(llm, "ollama_client", lambda: StubClient())
    result = llm.generate_answer("When is the examination?", [
        {"tool": "search_university_faq", "data": {"found": True, "results": [{"source": "Sample Examination Rules 2026", "text": "Question: exam rule\nAnswer: Sample rule.", "relevance": 0.9}]}},
        {"tool": "check_academic_calendar", "data": {"found": True, "records": [{"event_date": "2026-11-23"}]}},
    ])
    assert "not specified" not in result
    assert "November 23, 2026" in result
    assert "Sample Examination Rules 2026" not in result
    assert "backend/data/academic_calendar.json" not in result
    assert "[backend/data/academic_calendar.json]" not in result
    assert "[check_academic_calendar]" not in result
    assert "synthetic sample" in result.casefold()


def test_multi_tool_attendance_rules_and_next_class_answer_contains_both_sources(monkeypatch):
    class StubClient:
        def chat(self, **kwargs):
            return SimpleNamespace(message=SimpleNamespace(content="The timetable has a class on Friday."))

    monkeypatch.setattr(llm, "ollama_client", lambda: StubClient())
    result = llm.generate_answer("What are the attendance rules and when is my next DBMS class?", [
        {"tool": "search_university_faq", "data": {"found": True, "results": [{"passage": "Question: Minimum attendance requirement\nAnswer: Students need 75 percent attendance.", "text": "Question: Minimum attendance requirement\nAnswer: Students need 75 percent attendance."}]}},
        {"tool": "check_timetable", "data": {"found": True, "next_occurrence": "2026-11-20", "records": [{"subject": "DBMS", "day": "Friday", "start_time": "09:00", "end_time": "10:00", "room": "C-204"}]}},
    ])
    assert "75% attendance" in result
    assert "Friday, November 20, 2026" in result
    assert "09:00 to 10:00 in C-204" in result


def test_multi_tool_calendar_no_match_is_reported_alongside_class(monkeypatch):
    class StubClient:
        def chat(self, **kwargs):
            return SimpleNamespace(message=SimpleNamespace(content="The class is on Tuesday."))

    monkeypatch.setattr(llm, "ollama_client", lambda: StubClient())
    result = llm.generate_answer("Find my AI class on Tuesday and tell me whether any academic event is scheduled that day.", [
        {"tool": "check_timetable", "data": {"found": True, "records": [{"subject": "Artificial Intelligence (AI)", "day": "Tuesday", "start_time": "09:00", "end_time": "10:30", "room": "AI-Lab"}]}},
        {"tool": "check_academic_calendar", "input": {"weekday": "Tuesday"}, "data": {"found": False, "records": []}},
    ])
    assert "09:00 to 10:30 in AI-Lab" in result
    assert "no events listed for Tuesday" in result
