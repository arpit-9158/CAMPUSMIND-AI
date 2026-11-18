import logging
import uuid
import json
from collections import deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from backend.app.agents.graph import run_agent, stream_agent
from backend.app.config import get_settings
from backend.app.data import load_calendar, load_faq_csv, load_timetable
from backend.app.llm import check_llm, generate_answer
from backend.app.rag.ingestion import ingest_faq
from backend.app.rag.retriever import search_faq
from backend.app.rag.vector_store import get_collection

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("campusmind")
activity_log: deque[dict] = deque(maxlen=100)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("CampusMind AI API started")
    yield
    logger.info("CampusMind AI API stopped")


app = FastAPI(title="CampusMind AI API", description="Synthetic campus helpdesk API backed by Ollama, LangGraph, and persistent FAQ retrieval.", version="1.0.0", lifespan=lifespan)
settings = get_settings()
# Keep development CORS limited to the known Vite origins. Vite may use its
# default port (5173) or the project's configured port (5176).
development_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5176",
    "http://127.0.0.1:5176",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys([settings.frontend_origin, *development_origins])),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question cannot be blank")
        return value.strip()


class ChatResponse(BaseModel):
    answer: str
    tools_used: list[str]
    sources: list[dict]
    execution_summary: list[dict]
    tool_results: list[dict]
    session_id: str
    needs_clarification: bool = False


@app.exception_handler(Exception)
async def unexpected_error(_: Request, exc: Exception):
    logger.exception("Unhandled application exception", exc_info=exc)
    return JSONResponse(status_code=500, content={"error": "internal_server_error", "detail": "The request could not be completed. Check the server log for details."})


@app.get("/health")
def health():
    return {"status": "ok", "app": get_settings().app_name}


@app.get("/health/llm")
def llm_health():
    return check_llm()


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    session_id = str(uuid.uuid4())
    try:
        result = run_agent(body.question, session_id=session_id)
    except Exception as exc:
        logger.exception("Chat agent failed")
        raise HTTPException(status_code=503, detail={"error": "agent_unavailable", "message": f"Agent execution failed safely ({exc.__class__.__name__}). Please retry."}) from exc
    activity_log.appendleft({"session_id": session_id, "question": body.question, "tools_used": result["tools_used"], "tool_results": result["tool_results"], "execution_summary": result["execution_summary"], "answer": result["answer"]})
    return {"answer": result["answer"], "tools_used": result["tools_used"], "sources": result["sources"], "execution_summary": result["execution_summary"], "tool_results": result["tool_results"], "session_id": session_id, "needs_clarification": result.get("needs_clarification", False)}


@app.get("/agent/activity/{session_id}")
def agent_activity_session(session_id: str):
    record = next((item for item in activity_log if item["session_id"] == session_id), None)
    if not record:
        raise HTTPException(status_code=404, detail={"error": "session_not_found", "message": "No completed agent session was found."})
    return record


@app.post("/chat/stream")
def chat_stream(body: ChatRequest):
    session_id = str(uuid.uuid4())

    def events():
        try:
            for item in stream_agent(body.question, session_id=session_id):
                if item["type"] == "event":
                    yield f"event: agent_event\ndata: {json.dumps(item['event'], ensure_ascii=False)}\n\n"
                else:
                    result = item["result"]
                    record = {"session_id": session_id, "question": body.question, "tools_used": result["tools_used"], "tool_results": result["tool_results"], "execution_summary": result["execution_summary"], "sources": result["sources"], "answer": result["answer"], "needs_clarification": result["needs_clarification"]}
                    activity_log.appendleft(record)
                    yield f"event: final_answer\ndata: {json.dumps(record, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.exception("Streaming chat agent failed")
            error = {"session_id": session_id, "message": f"Agent execution failed safely ({exc.__class__.__name__}). Please retry."}
            yield f"event: error\ndata: {json.dumps(error)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/timetable")
def timetable(day: str | None = None, subject: str | None = None, semester: str | None = None, section: str | None = None):
    try:
        rows = load_timetable(get_settings().path(get_settings().timetable_json_path))
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=503, detail={"error": "timetable_unavailable", "message": str(exc)}) from exc
    records = [r for r in rows if (not day or r["day"].casefold() == day.casefold()) and (not subject or subject.casefold() in r["subject"].casefold()) and (not semester or str(r["semester"]) == semester) and (not section or str(r["section"]).casefold() == section.casefold())]
    return {"sample_data": True, "records": records, "count": len(records)}


@app.get("/calendar")
def calendar(event_type: str | None = None, upcoming: bool = False, on_date: str | None = None):
    try:
        rows = load_calendar(get_settings().path(get_settings().calendar_json_path))
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=503, detail={"error": "calendar_unavailable", "message": str(exc)}) from exc
    records = [r for r in rows if (not event_type or event_type.casefold() in r["event_type"].casefold())]
    if on_date:
        from datetime import date
        try:
            date.fromisoformat(on_date)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"error": "invalid_date", "message": "on_date must use YYYY-MM-DD format."}) from exc
        records = [r for r in records if r["event_date"] == on_date]
    if upcoming:
        from datetime import date
        records = [r for r in records if r["event_date"] >= date.today().isoformat()]
    records.sort(key=lambda r: r["event_date"])
    return {"sample_data": True, "records": records, "count": len(records)}


@app.get("/faqs")
def faqs(category: str | None = None, query: str | None = None):
    rows = load_faq_csv(get_settings().path(get_settings().faq_csv_path))
    if category:
        rows = [r for r in rows if r["category"].casefold() == category.casefold()]
    if query:
        terms = query.casefold().split()
        rows = [r for r in rows if any(term in f"{r['question']} {r['answer']} {r['category']}".casefold() for term in terms)]
    return {"sample_data": True, "records": rows, "categories": sorted({r["category"] for r in load_faq_csv(get_settings().path(get_settings().faq_csv_path))}), "count": len(rows)}


@app.get("/faqs/search")
def faq_search(question: str):
    try:
        return search_faq(question)
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"error": "faq_search_unavailable", "message": f"FAQ retrieval unavailable ({exc.__class__.__name__}). Run ingestion and retry."}) from exc


@app.post("/ingest")
def ingest(request: Request, rebuild: bool = False):
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(status_code=403, detail={"error": "local_only", "message": "Ingestion is restricted to local requests."})
    try:
        return ingest_faq(rebuild=rebuild)
    except Exception as exc:
        logger.exception("FAQ ingestion failed")
        raise HTTPException(status_code=503, detail={"error": "ingestion_failed", "message": str(exc)}) from exc


@app.get("/stats")
def stats():
    try:
        vector_count = get_collection().count()
        vector_status = "ready" if vector_count else "empty"
    except Exception:
        vector_count, vector_status = 0, "unavailable"
    return {"faq_records": len(load_faq_csv(get_settings().path(get_settings().faq_csv_path))), "faq_chunks": vector_count, "vector_store": vector_status, "tools": ["search_university_faq", "check_timetable", "check_academic_calendar", "generate_email_draft"], "llm": check_llm()}


@app.get("/activity")
def activity():
    return {"records": list(activity_log), "count": len(activity_log)}
