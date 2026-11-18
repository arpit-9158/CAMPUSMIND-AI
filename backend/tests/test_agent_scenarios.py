import pytest

from backend.app.agents import graph
from backend.app.agents.graph import run_agent


SCENARIOS = [
    ("What is the attendance requirement and when is my DBMS class on Monday?", ["search_university_faq", "check_timetable"]),
    ("When is the next examination, and what are the reappear examination rules?", ["search_university_faq", "check_academic_calendar"]),
    ("Who should I contact for a leave application and help me draft an email to them?", ["search_university_faq", "generate_email_draft"]),
    ("Find my AI class on Tuesday and tell me whether any academic event is scheduled that day.", ["check_timetable", "check_academic_calendar"]),
    ("Tell me the minimum attendance requirement, my next DBMS class, and the next examination date.", ["search_university_faq", "check_timetable", "check_academic_calendar"]),
]


@pytest.mark.parametrize("question,expected_tools", SCENARIOS)
def test_five_multistep_scenarios_execute_actual_tools(question, expected_tools, monkeypatch):
    # Keep scenario tests deterministic while exercising real FAQ retrieval, JSON tools, and the LangGraph execution path.
    monkeypatch.setattr(graph, "generate_answer", lambda question, evidence: "Verified evidence was retrieved from the requested campus sources.")
    result = run_agent(question)
    assert result["tools_used"] == expected_tools
    assert [entry["tool"] for entry in result["tool_results"]] == expected_tools
    assert result["answer"]
    assert any(event["type"] == "tool_completed" for event in result["execution_summary"])
    assert {"query_received", "agent_started", "tool_selected", "response_generating", "response_completed"} <= {event["event_type"] for event in result["execution_summary"]}
    assert all(event["event_id"] and event["session_id"] and event["timestamp"] and event["execution_summary"] is not None for event in result["execution_summary"])
    if "search_university_faq" in expected_tools:
        faq_result = next(r["data"] for r in result["tool_results"] if r["tool"] == "search_university_faq")
        assert faq_result["found"]
    if "check_timetable" in expected_tools:
        timetable_result = next(r["data"] for r in result["tool_results"] if r["tool"] == "check_timetable")
        assert timetable_result["found"]


def test_unavailable_information_uses_graceful_evidence_fallback(monkeypatch):
    monkeypatch.setattr(graph, "generate_answer", lambda question, evidence: (_ for _ in ()).throw(ConnectionError("Ollama unavailable")))
    result = run_agent("What class is scheduled on Sunday?")
    assert result["tools_used"] == ["check_timetable"]
    assert result["tool_results"][0]["data"]["found"] is False
    assert "No matching sample timetable record" in result["answer"]
    assert any(event["type"] == "response_fallback" for event in result["execution_summary"])


@pytest.mark.parametrize("question,expected_tools", [
    ("What is the minimum attendance requirement?", ["search_university_faq"]),
    ("When is my DBMS class on Monday?", ["check_timetable"]),
    ("What is my personal attendance percentage?", []),
    ("What is the attendance requirement and when is DBMS on Monday?", ["search_university_faq", "check_timetable"]),
    ("When is my next examination and what are the reappear rules?", ["search_university_faq", "check_academic_calendar"]),
])
def test_requested_intent_regressions(question, expected_tools, monkeypatch):
    monkeypatch.setattr(graph, "generate_answer", lambda question, evidence: "Answer uses only the retrieved synthetic sample evidence.")
    result = run_agent(question)
    assert result["tools_used"] == expected_tools
    assert [row["tool"] for row in result["tool_results"]] == expected_tools
    if "search_university_faq" in expected_tools:
        assert result["sources"]
        source = result["sources"][0]
        assert {"document_title", "category", "passage", "source_id", "retrieval_score"} <= source.keys()
    if "check_timetable" in expected_tools:
        assert result["tool_results"][-1]["data"]["found"]
    if question == "What is my personal attendance percentage?":
        assert "individual attendance records are not connected" in result["answer"]
        assert not any(char.isdigit() for char in result["answer"])


def test_ambiguous_dbms_attendance_requests_clarification_without_tools():
    result = run_agent("dbms attendance")
    assert result["tools_used"] == []
    assert result["needs_clarification"] is True
    assert "Do you mean" in result["answer"]
    assert result["tool_results"] == []


def test_tool_failure_is_observed_without_exposing_private_exception_details(monkeypatch):
    monkeypatch.setattr(graph, "check_timetable", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("private transport detail")))
    monkeypatch.setattr(graph, "generate_answer", lambda question, evidence: "Fallback based on safe failure information.")
    result = run_agent("When is my DBMS class on Monday?")
    failed = next(event for event in result["execution_summary"] if event["event_type"] == "tool_failed")
    assert failed["status"] == "failed"
    assert failed["tool_name"] == "check_timetable"
    assert "private transport detail" not in str(failed)
    assert failed["duration_ms"] >= 0


@pytest.mark.parametrize("question,expected_tools", [
    ("DBMS attendance requirement", ["search_university_faq"]),
    ("dbms attendence requirement", ["search_university_faq"]),
    ("What is the minimum attendance?", ["search_university_faq"]),
    ("What is the attendance percentage?", ["search_university_faq"]),
    ("How much attendance is needed for exams?", ["search_university_faq"]),
    ("What is my DBMS attendance?", []),
    ("Show my attendance percentage", []),
    ("When is my DBMS class?", ["check_timetable"]),
    ("What are the attendance rules and when is my next DBMS class?", ["search_university_faq", "check_timetable"]),
    ("When do my semester exams begin?", ["check_academic_calendar"]),
    ("Draft an email to my professor requesting leave.", ["generate_email_draft"]),
    ("What is the attendance criteria for end semester exams?", ["search_university_faq"]),
    ("What is the capital of Japan?", []),
])
def test_acceptance_intent_routes(question, expected_tools):
    assert [item["name"] for item in graph._choose_tools(question)] == expected_tools


@pytest.mark.parametrize("question", ["What is my DBMS attendance?", "Show my attendance percentage"])
def test_personal_attendance_is_transparent_and_never_invents_a_value(question):
    result = run_agent(question)
    assert result["tools_used"] == []
    assert "records are not connected" in result["answer"]
    assert "cannot see your actual attendance percentage" in result["answer"]
    assert not any(character.isdigit() for character in result["answer"])
    assert any(event["event_type"] == "response_fallback" for event in result["execution_summary"])


def test_email_intent_returns_the_actual_tool_draft_without_a_model_call(monkeypatch):
    monkeypatch.setattr(graph, "generate_answer", lambda *args: (_ for _ in ()).throw(AssertionError("Email-only drafting should use tool output directly.")))
    result = run_agent("Draft an email to my professor requesting leave.")
    assert result["tools_used"] == ["generate_email_draft"]
    assert result["tool_results"][0]["data"]["sent"] is False
    assert "Email draft — not sent" in result["answer"]
    assert "To: Professor" in result["answer"]
    assert "Subject:" in result["answer"]


def test_typo_normalization_retrieves_attendance_policy():
    result = graph.search_university_faq("DBMS attendence requirement")
    assert result["found"]
    assert any(hit["source_id"] == "faq-001" for hit in result["results"])


def test_unknown_query_gets_clarification_not_a_misleading_generic_failure():
    result = run_agent("What is the capital of Japan?")
    assert result["tools_used"] == []
    assert result["needs_clarification"] is True
    assert "Which campus topic should I look up?" in result["answer"]
