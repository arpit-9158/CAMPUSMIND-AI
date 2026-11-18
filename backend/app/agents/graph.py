import re
import time
import uuid
from typing import Any, TypedDict
from datetime import datetime, timezone

from langgraph.graph import END, START, StateGraph

from backend.app.llm import generate_answer
from backend.app.tools.calendar_tool import check_academic_calendar
from backend.app.tools.email_tool import generate_email_draft
from backend.app.tools.faq_tool import search_university_faq
from backend.app.tools.timetable_tool import check_timetable
from backend.app.rag.retriever import normalize_query

DAY_NAMES = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
SUBJECTS = ("dbms", "database management systems", "artificial intelligence", " ai ", "computer networks", "operating systems", "software engineering")


class AgentState(TypedDict, total=False):
    question: str
    plan: list[dict[str, Any]]
    results: list[dict[str, Any]]
    events: list[dict[str, Any]]
    answer: str
    sources: list[dict[str, Any]]
    direct_answer: str
    needs_clarification: bool
    session_id: str


def _choose_tools(question: str) -> list[dict[str, Any]]:
    normalized_question = normalize_query(question)
    q = normalized_question.casefold()
    plan: list[dict[str, Any]] = []
    day = next((d.title() for d in DAY_NAMES if re.search(rf"\b{d}\b", q)), None)
    subject = next((s for s in SUBJECTS if s in q), None)
    subject = {"dbms": "DBMS", "database management systems": "DBMS", "artificial intelligence": "AI", " ai ": "AI", "computer networks": "Computer Networks", "operating systems": "Operating Systems", "software engineering": "Software Engineering"}.get(subject, subject)

    # Student-specific attendance records are deliberately absent from the sample corpus.
    # Handle them before topic matching so a course name cannot trigger an unrelated lookup.
    attendance = bool(re.search(r"\b(attendance|attend)\b", q))
    personal_reference = bool(re.search(r"\b(my|mine|personal|individual|current)\b", q))
    policy_cue = bool(re.search(r"\b(minimum|requirement|required|needed|policy|criteria|eligible|eligibility|shortage|condonation|percentage|percent|rules?|for exams?|end[- ]semester)\b", q))
    personal_policy_cue = bool(re.search(r"\b(minimum|requirement|required|needed|policy|criteria|eligible|eligibility|shortage|condonation|rules?|for exams?|end[- ]semester)\b", q))
    if attendance and personal_reference and not personal_policy_cue:
        return []

    attendance_policy = attendance and policy_cue
    timetable_cue = bool(re.search(r"\b(timetable|schedule|lecture|class|when is|when does|what time|class timing|classroom)\b", q))
    # “DBMS attendance” does not establish whether the user asks about policy or a class slot.
    if attendance and subject and not attendance_policy and not timetable_cue:
        return []

    email_intent = bool(re.search(r"\b(draft|write|compose|request|prepare)\b.*\b(email|message|application)\b|\b(email|application)\b.*\b(draft|write|compose|request|prepare)\b", q))
    faq_terms = bool(re.search(r"\b(policy|rules?|reappear|library|hostel|scholarship|placement|transcript|fee|contact|department|handbook|assignment)\b", q))
    leave_faq = "leave" in q and bool(re.search(r"\b(who|contact|application process|apply|where)\b", q))
    faq_intent = attendance_policy or faq_terms or leave_faq
    if faq_intent:
        faq_query = normalized_question
        focused_topics = []
        if attendance_policy:
            focused_topics.append("minimum attendance requirement")
        if "reappear" in q:
            focused_topics.append("reappear examination rules")
        if "leave" in q and re.search(r"\b(contact|application|apply)\b", q):
            focused_topics.append("Who should I contact for a leave application?")
        if focused_topics:
            faq_query = " ".join(focused_topics)
        plan.append({"name": "search_university_faq", "input": {"question": faq_query}})
    if timetable_cue and (day or subject or re.search(r"\b(class|timetable|lecture|schedule)\b", q)):
        plan.append({"name": "check_timetable", "input": {"day": day, "subject": subject, "upcoming": bool(re.search(r"\b(next|upcoming)\b", q) and subject)}})
    calendar_reference = bool(re.search(r"\b(calendar|events?|holidays?|semester dates?|semester break|scheduled that day)\b", q))
    dated_exam_intent = bool(re.search(r"\b(examinations?|exams?)\b", q) and re.search(r"\b(next|upcoming|when|begin|start|date|dates|schedule)\b", q))
    calendar_intent = calendar_reference or dated_exam_intent
    if calendar_intent:
        event_type = "Examination" if re.search(r"\b(examinations?|exams?)\b", q) else None
        on_weekday = day if re.search(r"\b(event|calendar|scheduled)\b", q) and re.search(r"\b(that day|same day|on that)\b", q) else None
        plan.append({"name": "check_academic_calendar", "input": {"on_date": None, "event_type": event_type, "upcoming": bool(event_type or re.search(r"\b(next|upcoming|when|begin|start)\b", q)), "weekday": on_weekday}})
    if email_intent:
        match = re.search(r"(?:about|for|regarding)\s+(.+?)(?:\s+and\s+|$)", question, re.I)
        purpose = (match.group(1).strip(" .?!") if match else "leave") if "leave" in q else (match.group(1).strip(" .?!") if match else "your request")
        recipient = "Professor" if re.search(r"\b(professor|lecturer|instructor)\b", q) else "Department Office"
        plan.append({"name": "generate_email_draft", "input": {"recipient_role": recipient, "subject": f"Request regarding {purpose}", "purpose": purpose}})
    return plan


def _planning_node(state: AgentState) -> AgentState:
    question = state["question"]
    plan = _choose_tools(question)
    normalized_question = normalize_query(question)
    personal = bool(re.search(r"\b(attendance|attend)\b", normalized_question, re.I) and re.search(r"\b(my|mine|personal|individual|current)\b", normalized_question, re.I) and not re.search(r"\b(minimum|requirement|required|needed|policy|criteria|eligible|eligibility|shortage|condonation|rules?|for exams?|end[- ]semester)\b", normalized_question, re.I))
    ambiguous = bool(re.search(r"\b(attendance|attend)\b", normalized_question, re.I) and re.search(r"\b(dbms|database management systems|artificial intelligence|computer networks|operating systems|software engineering)\b", normalized_question, re.I) and not personal and not re.search(r"\b(minimum|requirement|required|needed|policy|criteria|eligible|eligibility|shortage|condonation|percentage|percent|rules?|for exams?|end[- ]semester|timetable|schedule|lecture|class|when is|what time)\b", normalized_question, re.I))
    unsupported = not plan and not personal and not ambiguous
    direct = "I can explain the DBMS attendance requirement, but your individual attendance records are not connected to CampusMind AI yet. I cannot see your actual attendance percentage." if personal else "Do you mean the attendance requirement for DBMS, or when the DBMS class meets?" if ambiguous else "I can help with campus policies, class schedules, academic dates, and email drafts. Which campus topic should I look up?" if unsupported else ""
    event_time = datetime.now(timezone.utc).isoformat()
    events = [{"type": "query_received", "status": "completed", "detail": question, "timestamp": event_time}, {"type": "agent_started", "status": "completed", "timestamp": event_time}, {"type": "tool_selected", "status": "completed", "tools": [p["name"] for p in plan], "timestamp": event_time}]
    if direct:
        reason = "personal_records_unavailable" if personal else "ambiguous_attendance_intent" if ambiguous else "unsupported_or_unclear_intent"
        events.append({"type": "response_fallback" if personal else "clarification_requested", "status": "completed", "reason": reason})
    return {"plan": plan, "results": [], "sources": [], "direct_answer": direct, "needs_clarification": ambiguous or unsupported, "events": events}


def _execute_node(state: AgentState) -> AgentState:
    functions = {"search_university_faq": search_university_faq, "check_timetable": check_timetable, "check_academic_calendar": check_academic_calendar, "generate_email_draft": generate_email_draft}
    results, events, sources = [], list(state.get("events", [])), []
    for action in state.get("plan", []):
        name, inputs = action["name"], action["input"]
        events.append({"type": "tool_started", "tool": name, "status": "running", "execution_summary": f"Started {name.replace('_', ' ')}.", "timestamp": datetime.now(timezone.utc).isoformat()})
        started = time.perf_counter()
        try:
            data = functions[name](**inputs)
            result = {"tool": name, "input": inputs, "data": data}
            results.append(result)
            if name == "search_university_faq":
                sources.extend(data.get("results", []))
            events.append({"type": "tool_completed", "tool": name, "status": "completed", "duration_ms": round((time.perf_counter() - started) * 1000, 2), "safe_result_summary": _safe_result_summary(name, data), "timestamp": datetime.now(timezone.utc).isoformat()})
        except Exception as exc:
            data = {"found": False, "message": "Tool failed safely. Please retry or use the corresponding data page."}
            results.append({"tool": name, "input": inputs, "data": data, "error": True})
            events.append({"type": "tool_failed", "tool": name, "status": "failed", "error": exc.__class__.__name__, "duration_ms": round((time.perf_counter() - started) * 1000, 2), "safe_result_summary": f"Tool failed safely ({exc.__class__.__name__}).", "timestamp": datetime.now(timezone.utc).isoformat()})
    return {"results": results, "events": events, "sources": sources}


def _answer_node(state: AgentState) -> AgentState:
    events = state.get("events", [])
    results = state.get("results", [])
    response_started = time.perf_counter()
    events.append({"type": "response_generating", "status": "running", "execution_summary": "Preparing a concise response from the available evidence.", "timestamp": datetime.now(timezone.utc).isoformat()})
    if state.get("direct_answer"):
        answer = state["direct_answer"]
    elif not results:
        answer = "I can help with campus policies, class schedules, academic dates, and email drafts. Which campus topic should I look up?"
    elif len(results) == 1 and results[0]["tool"] == "generate_email_draft":
        draft = results[0]["data"]
        answer = f"{draft['label']}\nTo: {draft['recipient_role']}\nSubject: {draft['subject']}\n\n{draft['body']}"
    else:
        try:
            answer = generate_answer(state["question"], results)
        except Exception as exc:
            details = []
            for item in results:
                data = item["data"]
                if item["tool"] == "search_university_faq" and data.get("found"):
                    details.extend(hit["text"] for hit in data["results"])
                elif item["tool"] == "check_timetable" and data.get("found"):
                    details.extend(f"{r['day']} {data.get('next_occurrence') or ''} {r['start_time']}-{r['end_time']}: {r['subject']} with {r['faculty']} in {r['room']} (synthetic sample timetable)." for r in data["records"])
                elif item["tool"] == "check_academic_calendar" and data.get("found"):
                    details.extend(f"{r['event_name']} on {r['event_date']} ({r['event_type']}; synthetic sample calendar)." for r in data["records"])
                elif item["tool"] == "generate_email_draft":
                    details.append(str(data))
                elif data.get("message"):
                    details.append(data["message"])
            answer = "\n".join(details) if details else "I couldn't find reliable information in the available sample university data. Please contact your department administration for confirmation."
            events.append({"type": "response_fallback", "status": "completed", "reason": f"LLM unavailable ({exc.__class__.__name__})"})
    events.append({"type": "response_completed", "status": "completed", "duration_ms": round((time.perf_counter() - response_started) * 1000, 2), "execution_summary": "Response is ready.", "timestamp": datetime.now(timezone.utc).isoformat()})
    return {"answer": answer, "events": events}


def _safe_result_summary(tool: str, data: dict[str, Any]) -> str:
    if tool == "search_university_faq":
        return f"Retrieved {len(data.get('results', []))} FAQ passage(s)." if data.get("found") else "No reliable FAQ passage matched."
    if tool == "check_timetable":
        rows = data.get("records", [])
        return f"Found {len(rows)} matching timetable record(s)." if rows else "No matching timetable records."
    if tool == "check_academic_calendar":
        rows = data.get("records", [])
        return f"Found {len(rows)} matching calendar event(s)." if rows else "No matching calendar events."
    if tool == "generate_email_draft":
        return "Generated an email draft; it was not sent."
    return "Tool completed."


def _event_records(events: list[dict[str, Any]], session_id: str) -> list[dict[str, Any]]:
    enriched = []
    for index, event in enumerate(events):
        event_type = event.get("type", "agent_event")
        item = {**event, "event_id": event.get("event_id") or f"{session_id}:{index + 1}", "session_id": session_id, "event_type": event_type, "tool_name": event.get("tool"), "timestamp": event.get("timestamp") or datetime.now(timezone.utc).isoformat(), "execution_summary": event.get("execution_summary") or event.get("detail") or (f"{event.get('tool', 'Agent')} {event.get('status', 'completed')}."), "safe_result_summary": event.get("safe_result_summary", "")}
        enriched.append(item)
    return enriched


graph_builder = StateGraph(AgentState)
graph_builder.add_node("plan", _planning_node)
graph_builder.add_node("execute_tools", _execute_node)
graph_builder.add_node("compose_answer", _answer_node)
graph_builder.add_edge(START, "plan")
graph_builder.add_edge("plan", "execute_tools")
graph_builder.add_edge("execute_tools", "compose_answer")
graph_builder.add_edge("compose_answer", END)
campus_agent = graph_builder.compile()


def run_agent(question: str, session_id: str | None = None) -> dict[str, Any]:
    session_id = session_id or str(uuid.uuid4())
    state = campus_agent.invoke({"question": question})
    events = _event_records(state.get("events", []), session_id)
    return {"answer": state["answer"], "tools_used": [p["name"] for p in state.get("plan", [])], "sources": state.get("sources", []), "execution_summary": events, "tool_results": state.get("results", []), "needs_clarification": state.get("needs_clarification", False), "session_id": session_id}


def stream_agent(question: str, session_id: str | None = None):
    session_id = session_id or str(uuid.uuid4())
    seen = 0
    state: dict[str, Any] = {}
    for update in campus_agent.stream({"question": question}, stream_mode="updates"):
        for node_state in update.values():
            state.update(node_state)
        events = _event_records(state.get("events", []), session_id)
        for event in events[seen:]:
            yield {"type": "event", "event": event}
        seen = len(events)
    yield {"type": "result", "result": {"answer": state.get("answer", ""), "tools_used": [p["name"] for p in state.get("plan", [])], "sources": state.get("sources", []), "execution_summary": _event_records(state.get("events", []), session_id), "tool_results": state.get("results", []), "needs_clarification": state.get("needs_clarification", False), "session_id": session_id}}
