# CampusMind AI Testing Report

**Execution date:** 2026-11-17. This report records test and HTTP output produced by running the implementation in this workspace. Current intent-regression requests are summarized in [`live-regression-evidence.json`](live-regression-evidence.json), and live SSE/session output is in [`live-stream-evidence.json`](live-stream-evidence.json). Older initial traces remain in `live-scenarios.json`.

## Results

| Verification | Result | Evidence |
|---|---|---|
| Dataset validation | **PASS** | `python -m backend.app.cli validate` returned `valid: true`, 40 FAQ records, 16 timetable records, 12 calendar events. |
| Data ingestion | **PASS** | `python -m backend.app.cli ingest --rebuild` embedded 40 chunks in persistent collection `campus_faq`. |
| Chroma persistence | **PASS** | A separately started API process returned `/stats`: 40 records, 40 chunks, `vector_store: ready`. |
| Grounded FAQ retrieval | **PASS** | Semantic attendance search returned FAQ `faq-001`, containing “at least 75 percent”, with source `Sample Student Handbook 2026`. |
| Exact Llama model | **PASS** | `ollama list` includes `llama3.2:3b`; `/health/llm` reports `available: true` for exact tag `llama3.2:3b`. |
| Real model prompt | **PASS** | `ollama run llama3.2:3b "Answer in one sentence: what is the capital of France?"` returned “The capital of France is Paris.” |
| Intent regression scenarios | **PASS** | Five live HTTP requests returned the expected FAQ/timetable/calendar tools or safe no-tool personal-record response. See `live-regression-evidence.json`. |
| FastAPI HTTP + SSE | **PASS** | Health, model health, stats, timetable (16), calendar (12), FAQs (40), activity, stream, and session lookup returned usable responses. See `live-stream-evidence.json`. |
| Error handling | **PASS** | Live no-result Sunday timetable query returned a truthful no-match answer. Blank chat input returned HTTP 422 with Pydantic validation detail. Invalid calendar date returned HTTP 422 with `invalid_date`. |
| Frontend build | **PASS** | `npm run build` — TypeScript check and Vite production bundle. |
| Frontend serving | **PASS** | Vite development server started at `http://127.0.0.1:5173/`; HTTP GET returned 200. |
| Frontend dependencies | **PASS** | `npm audit --audit-level=moderate` returned zero known vulnerabilities after upgrading React Router. |
| Automated tests | **PASS** | `.venv\Scripts\python.exe -m pytest backend/tests -q` — **42 passed**. Deterministic tests use actual Chroma/JSON tools with mocked synthesis only; live regression requests used the actual Ollama model. |

## Initial five multi-tool scenario traces (archival)

The current priority regression queries are listed in `live-regression-evidence.json`; this earlier set covers the original five multi-tool acceptance scenarios.

All entries below were POSTed through the running Uvicorn server. Each raw response includes session ID, selected tool names, tool inputs, outputs, timing/status events, sources, and answer.

| # | Query | Tools actually called | Verified data returned |
|---|---|---|---|
| 1 | Attendance requirement and Monday DBMS | `search_university_faq`, `check_timetable` | FAQ `faq-001`: minimum 75 percent; timetable `class-001`: Monday 09:00–10:00, C-204. |
| 2 | Next examination and reappear rules | `search_university_faq`, `check_academic_calendar` | FAQ `faq-013` / `faq-014` reappear rules; next matching sample exam event: Internal Assessment 2 on 2026-11-23. |
| 3 | Leave contact and draft email | `search_university_faq`, `generate_email_draft` | FAQ `faq-018`: department office and `cse.office@example.edu`; generated draft marked not sent. |
| 4 | AI Tuesday class and same-day event | `check_timetable`, `check_academic_calendar` | `class-005`: Tuesday 09:00–10:30 in AI-Lab; no event record matched Tuesday in sample calendar JSON. |
| 5 | Attendance, next DBMS class, next exam | `search_university_faq`, `check_timetable`, `check_academic_calendar` | 75 percent attendance; next recurring DBMS slot calculated from timetable: Wednesday 2026-11-18 12:00–13:00 C-204; Internal Assessment 2 on 2026-11-23. |

### Current regression answer excerpts

- **Attendance policy:** FAQ RAG only; retrieved `faq-001` with score 0.6869 and answered the sample 75% threshold.
- **Personal attendance:** No tools and no fabricated records; the assistant explicitly says individual attendance records are unavailable.
- **Attendance + Monday DBMS:** FAQ RAG plus timetable; returned 75% and Monday 09:00–10:00 in C-204.
- **Next examination + reappear rules:** FAQ RAG plus calendar; returned Internal Assessment 2 on November 23, 2026 and the retrieved sample rule passage.

The multi-tool SSE check emitted actual FAQ and timetable events with measured durations, then returned the structured FAQ source and combined answer; see `live-stream-evidence.json`.

## Failure case

Live HTTP request: `POST /chat` with `{"question":"What class is scheduled on Sunday?"}`. The `check_timetable` tool ran against the timetable JSON, returned `found: false`, and the response stated that no matching sample timetable record was found. A whitespace-only question returned HTTP **422** with `Question cannot be blank`; malformed calendar date returned HTTP **422** with `invalid_date`. This demonstrates fallback and input validation without inventing a class.

## Issues found and fixed during implementation

1. A comma in an unquoted FAQ answer caused Pandas CSV tokenization to fail. Replaced the comma with a semicolon and reran validation/ingestion.
2. Initial Vite dependency selection paired `@vitejs/plugin-react@latest` (Vite 8 peer range) with Vite 6. Pinned the compatible plugin version; npm install and build then succeeded.
3. Initial TypeScript build exposed missing Vite `ImportMeta.env` declarations and a target too old for `String.replaceAll`. Added `vite-env.d.ts`, used ES2021, and removed the unused import.
4. Initial live answers included unrelated FAQ citations and occasionally said an event date was missing while naming it. Focused FAQ queries, raised relevance threshold, enforced evidence-based citations, and added deterministic completion for dates and negative calendar lookups. Re-ran all five actual scenarios.
5. `npm audit` identified two moderate React Router advisories. Upgraded to the compatible React Router 7 release; audit then reported zero vulnerabilities.

## Test inventory

The 42 pytest cases cover CSV schema/cleaning/duplicates/date checks; JSON validity; timetable/calendar filtering; email draft safety; intent route-and-tool scenarios; event schema and tool failures; Chroma persistence and semantic grounding; structured RAG metadata; answer fallback behavior; API health/data endpoints; SSE and per-session activity; invalid input/date handling; and FAQ browsing. Ollama generation was also verified in live HTTP regression requests against the configured model.
