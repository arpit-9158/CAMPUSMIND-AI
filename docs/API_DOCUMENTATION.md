# API Documentation

Base URL: `http://127.0.0.1:8000` (Swagger UI: `/docs`).

## `POST /chat`

Request: `{"question":"What is the attendance requirement and when is my DBMS class on Monday?"}`

The response schema is:

```json
{
  "answer": "...concise answer grounded in actual tool evidence...",
  "tools_used": ["search_university_faq", "check_timetable"],
  "sources": [{"document_title":"Sample Student Handbook 2026","category":"Attendance","passage":"Question: ...\\nAnswer: ...","source_id":"faq-001","document_id":"faq-001-0","retrieval_score":0.8,"distance":0.2,"score_type":"1 - cosine distance (higher is more relevant)","metadata":{"faq_id":"faq-001","last_updated":"2026-08-01"}}],
  "execution_summary": [{"event_id":"...:5","session_id":"...","event_type":"tool_completed","tool_name":"check_timetable","status":"completed","timestamp":"2026-11-17T00:00:00+00:00","execution_summary":"check timetable completed.","safe_result_summary":"Found 1 matching timetable record(s).","duration_ms":1.2}],
  "tool_results": [{"tool":"check_timetable","input":{"day":"Monday","subject":"DBMS"},"data":{"found":true,"records":["actual matching JSON records"]}}],
  "session_id": "uuid"
}
```

FAQ `sources` contain only documents actually retrieved from ChromaDB. Timetable and calendar records appear in `tool_results` as separate tool evidence. FAQ relevance is `1 - cosine distance` (higher is more relevant). For an ambiguous query such as `dbms attendance`, the answer is a concise clarification and no tool runs. Personal attendance questions state that the synthetic dataset has no individual records. Whitespace-only questions return 422. Agent failures return 503 with a structured detail object. Current live regression and stream evidence are in [`live-regression-evidence.json`](live-regression-evidence.json) and [`live-stream-evidence.json`](live-stream-evidence.json).

## `POST /chat/stream`

Accepts the same `{"question":"..."}` body as `/chat` and returns `text/event-stream`. Events are `agent_event` records emitted from LangGraph execution followed by one `final_answer` event. A failure emits an `error` event. Example event names: `query_received`, `agent_started`, `tool_selected`, `tool_started`, `tool_completed`, `tool_failed`, `response_generating`, and `response_completed`.

## `GET /agent/activity/{session_id}`

Returns the actual completed session with question, answer, tool outputs, FAQ sources, and timestamped observable execution events. Unknown sessions return 404. `/activity` remains the recent-session feed.

## Other endpoints

- `GET /health` — application liveness.
- `GET /health/llm` — checks Ollama service and the exact configured model tag; never aliases another model.
- `GET /timetable?day=Monday&subject=DBMS&semester=5&section=A` — filters sample JSON records.
- `GET /calendar?event_type=Examination&upcoming=true&on_date=2026-11-23` — filters sample calendar records; invalid ISO dates return 422.
- `GET /faqs?category=Attendance&query=minimum` — browse FAQ CSV rows.
- `GET /faqs/search?question=minimum%20attendance` — semantic Chroma search with sources and relevance.
- `POST /ingest?rebuild=true` — trigger ingestion from loopback only.
- `GET /stats` — source record count, vector chunk count, tools, and LLM status.
- `GET /activity` — recent actual tool execution records held in process memory.

See `postman/CampusMind_AI.postman_collection.json` for importable requests.
