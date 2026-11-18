# CampusMind AI — Functional Acceptance Audit

**Audit date:** 2026-11-18 (Asia/Kolkata)  
**Scope:** Existing React/Vite frontend, FastAPI API, LangGraph execution, Ollama, ChromaDB and bundled campus data.  
**Test approach:** Live HTTP requests against the running app, direct data endpoint checks, live Llama calls, SSE checks, backend regression tests and a production build.

## Executive result

The backend data endpoints, configured Llama model, persisted FAQ collection, four tools and tested assistant intents are working. The audit found and fixed several routing and answer-composition bugs, including the reported “attendence” failure. All 62 backend tests pass, the frontend production build passes, and the five pre-existing live agent scenarios returned HTTP 200 with the expected tool executions.

The audit is **PARTIAL overall**. LLM-backed answers take roughly 8–33 seconds in the live sample. The stream works but the frontend does not reconnect automatically. Intent classification still uses deterministic patterns without an LLM classification fallback. Browser screenshots, rendered UI behavior and browser console errors could not be verified: the computer-use browser control stopped because it could not establish the current browser URL safely. Voice features are not present.

## Acceptance results

| Test | Status | Evidence and result |
|---|---|---|
| 1. Dashboard | **PARTIAL** | Backend-backed totals were verified: 40 FAQs, 40 chunks, 16 timetable entries, 12 events, four tools, and `llama3.2:3b` available. Frontend code fetches these API values; visual card rendering was not inspected in a browser. |
| 2. Assistant | **PASS** for requested prompts | Live `/chat` calls returned 200. Attendance policy, misspelling, timetable, calendar, FAQ, email, personal attendance, multi-tool and unrelated-question cases were exercised. Actual traces and the remaining classifier limitation are below. |
| 3. Timetable | **PASS** for API behavior | `/timetable` returned all 16 rows across Monday–Friday. Monday filter returned four rows; Sunday returned zero. Every row had subject, faculty, room and start/end times. An explicit UI empty state was added; visual rendering was not inspected. |
| 4. Academic calendar | **PASS** for API behavior | `/calendar` returned 12 events in ascending date order from 2026-08-03 through 2027-05-10. Categories present: Academic, Examination, Holiday and Registration. |
| 5. FAQ Explorer | **PASS** for API behavior | `/faqs` returned 40 records and 15 categories. Attendance category returned four records; a nonexistent query returned zero. Source fields are present. A visible empty-results message was added; visual rendering was not inspected. |
| 6. Agent Activity | **PARTIAL** | Live streamed events and session detail were verified. Tool durations are captured from timed executions. UI filtering is implemented in the frontend code. Automatic stream reconnection is not implemented, and UI filtering was not exercised in a browser. |
| 7. Settings | **PASS** for backend checks | `/health` and `/health/llm` returned 200; Ollama reported `llama3.2:3b` available. `/stats` reported the persistent Chroma collection ready with 40 chunks and all four tools. Settings card rendering was not visually inspected. |
| 8. Performance | **PARTIAL** | API, retrieval/tool and response-generation time were measured. Live LLM generation is slow (8–33 seconds); the LLM dominates end-to-end time. No concurrent-load benchmark was run. |
| 9. Voice Assistant | **NOT IMPLEMENTED** | No microphone, recording, STT, English/Hindi transcription, TTS, interruption, playback or audio deletion implementation was found in frontend or backend source. |
| 10. Regression | **PARTIAL** | 62 backend tests passed; `npm run build` passed; five live agent scenarios passed; seven frontend route URLs returned HTTP 200 from Vite. No frontend test script exists, browser rendering and browser console were not inspected. |

## Test details

### Dashboard and Settings APIs

All inspected endpoints returned HTTP 200:

| Endpoint | Result |
|---|---|
| `GET /health` | `status: ok` |
| `GET /health/llm` | `available: true`, model `llama3.2:3b` |
| `GET /stats` | 40 FAQ records, 40 chunks, vector store `ready`, four registered tools |
| `GET /timetable` | 16 records |
| `GET /calendar` | 12 records |
| `GET /faqs` | 40 records |
| `GET /activity` | Completed in-memory sessions returned |

ChromaDB is configured with `PersistentClient` and an on-disk `backend/chroma_db` directory. The live server returned all 40 existing vectors after a separate API process was started, confirming the data was available from the persisted store.

### Assistant and routing

The original deterministic router missed common language variants. Live baseline requests showed:

- “dbms attendence requirement” selected no tool and returned a generic fallback; direct RAG search returned HTTP 200 with no matches.
- “How much attendance is needed for exams?”, “When do my semester exams begin?” and “attendance criteria for end semester exams” selected no tool.
- “What is my DBMS attendance?” incorrectly asked whether the user meant policy or class time.
- “What are the attendance rules and when is my next DBMS class?” selected only the timetable tool.
- Email drafting selected an irrelevant FAQ search, and the missing FAQ match suppressed the draft output.
- A calendar lookup with no matching event did not state the no-event result in a combined answer.

These were fixed, then retested against a fresh live API process. Results:

| Question | Live result |
|---|---|
| “DBMS attendence requirement” | HTTP 200; `search_university_faq`; retrieved `faq-001` from *Sample Student Handbook 2026*, score **0.6869**; answer included the 75% sample policy. |
| “What is the minimum attendance?” | HTTP 200; FAQ tool; `faq-001`, score **0.6869**; grounded 75% answer. |
| “What is the attendance percentage?” | Automated routing regression confirms general percentage questions select the FAQ policy tool; a personal possessive variant remains on the no-records path. |
| “How much attendance is needed for exams?” | HTTP 200; FAQ tool; `faq-001`, score **0.6869**. |
| “What is my DBMS attendance?” | HTTP 200; no tools; states that personal records are not connected and that it cannot see the user’s actual percentage. No personal value was invented. |
| “Show my attendance percentage” | HTTP 200; same transparent personal-record fallback; no numeric value. |
| “When is my DBMS class?” | HTTP 200; timetable tool returned the DBMS class and its actual schedule record. |
| “What are the attendance rules and when is my next DBMS class?” | HTTP 200; FAQ and timetable tools both completed; answer included the 75% requirement and the next class on Friday, November 20, 2026, 09:00–10:00, C-204. |
| “When do my semester exams begin?” | HTTP 200; calendar tool returned Internal Assessment 2 on November 23, 2026. Answer labeled the data synthetic. |
| “Draft an email to my professor requesting leave.” | HTTP 200; only `generate_email_draft` ran. Actual draft output included recipient, subject and body; `sent: false`. |
| “What is the attendance criteria for end semester exams?” | HTTP 200; FAQ tool only, with `faq-001` and the 75% result. |
| “What is the capital of Japan?” | HTTP 200; no tools; helpful clarification directs the user to campus information topics. |

The five pre-existing live agent scenarios also returned HTTP 200:

1. Attendance requirement + Monday DBMS class: FAQ and timetable both found records; answer included both facts.
2. Next examination + reappear rules: FAQ and calendar both found records; answer included Internal Assessment 2 on November 23 and the retrieved reappear rule.
3. Leave contact + email draft: FAQ and email tools both ran; answer included `cse.office@example.edu` and an unsent draft.
4. Tuesday AI class + academic event: timetable found the 09:00–10:30 AI-Lab class; calendar returned no Tuesday event; answer stated both results.
5. Attendance + next DBMS class + next exam: all three tools ran and found results; answer included the 75% policy, Friday DBMS slot and November 23 exam.

### Data explorer checks

The timetable contains 16 valid records, Monday through Friday, with populated subject, faculty, room, start and end time fields. Monday returned four rows. Sunday returned zero rows. The React timetable now presents an explicit “No classes scheduled” empty state.

The calendar contains 12 chronologically ordered records. Its dates are `2026-08-03`, `2026-08-14`, `2026-09-14`, `2026-10-19`, `2026-11-23`, `2026-12-14`, `2026-12-28`, `2026-12-30`, `2027-01-18`, `2027-01-20`, `2027-03-15` and `2027-05-10`.

FAQ checks confirmed all 40 rows, 15 categories, four Attendance records and zero rows for a deliberately unmatched search. Search results include the source filename/metadata. The assistant response includes the retrieved source and numeric retrieval score in its response payload; the frontend renders both. The FAQ Explorer now presents an explicit “No matching FAQs” empty state.

### Agent Activity and streaming

`POST /chat/stream` returned HTTP 200 with `text/event-stream`. A personal-attendance execution emitted `agent_event` entries followed by `final_answer`. `GET /agent/activity/{session_id}` returned HTTP 200 for that completed session. Its actual event sequence was `query_received`, `agent_started`, `tool_selected`, `response_fallback`, `response_generating`, `response_completed`.

Live tool sessions emitted `tool_started` and `tool_completed`; successful tool durations were recorded with `time.perf_counter()`. Example warm execution times were roughly 50–65 ms for FAQ retrieval and under 2 ms for timetable/calendar local lookups. The activity page polls completed sessions every 2.5 seconds and filters by session ID or query in frontend code. The streaming client has no retry/reconnection logic; a dropped stream surfaces as an error instead.

## Performance measurements

Measurements are individual local HTTP samples, not a load test.

| Operation | Measured time |
|---|---:|
| `GET /timetable` | 7.22 ms |
| `GET /calendar` | 5.15 ms |
| `GET /faqs` | 68.72 ms |
| `GET /activity` | 21.17 ms |
| `GET /health/llm` | 2.41 s |
| `GET /stats` | 2.40 s |
| FAQ retrieval after warm-up | 51–65 ms in observed runs |
| Cold embedding initialization + first retrieval | about 4.7–5.2 s |
| Live chat end-to-end | 8.4–32.5 s across the five existing scenarios |
| Live response-generation event | 6.6–21.2 s in observed cases |

The Llama response-generation step dominates chat latency. FAQ embedding model initialization adds a one-time delay on a fresh process. Tool/data lookups are short once initialized. The measured response time is high for interactive chat and is the main remaining performance limitation.

## Regression results

- `python -m pytest backend/tests -q`: **62 passed**.
- `npm run build`: **passed** (`tsc -b` and Vite production build).
- Five existing multi-tool scenarios: **five HTTP 200 responses**, expected tools completed, grounded results returned.
- Vite route smoke checks returned HTTP 200 for `/`, `/assistant`, `/timetable`, `/academic-calendar`, `/faq-explorer`, `/agent-activity` and `/settings`.
- The frontend `package.json` has no test script, so there are no frontend automated tests to run.
- Browser console errors and pixel-level rendering were not tested. The browser-control tool stopped before inspection because it could not establish the current browser URL safely; no screenshots are attached.

## Root causes and fixes applied

1. Intent matching used narrow singular keywords and did not normalize “attendence”, “rules”, “criteria”, “needed” or plural exam phrasing. Added common spelling normalization and explicit intent cues while retaining the original user query for session display/logging.
2. FAQ search embedded the raw misspelling and kept the query below the existing relevance threshold. Attendance policy queries now use the canonical “minimum attendance requirement” retrieval phrase. The relevance threshold remains unchanged; the retrieved source and score remain actual Chroma results.
3. Personal attendance detection required a numeric/record term and failed on “What is my DBMS attendance?” Personal references now take precedence unless the user clearly asks for policy, and the response transparently says records are not connected.
4. Generic leave phrasing incorrectly triggered FAQ retrieval and caused the no-evidence guard to hide email output. Plain draft requests now route to the existing email tool and return its actual unsent draft. A combined contact-and-draft request still runs both applicable tools.
5. The verified answer composer recognized only narrow attendance terms and did not report empty calendar matches when combined with timetable results. It now composes both attendance and next-class evidence and states when a weekday calendar lookup has no results.
6. Timetable and FAQ list pages lacked explicit empty-result messages. Added empty states without replacing their existing data paths.

Files changed:

- `backend/app/agents/graph.py`
- `backend/app/rag/retriever.py`
- `backend/app/llm.py`
- `backend/tests/test_agent_scenarios.py`
- `backend/tests/test_llm.py`
- `frontend/src/App.tsx`
- `FINAL_FUNCTIONAL_AUDIT.md`

## Remaining limitations

- Intent classification is still deterministic keyword/rule based. The requested acceptance prompts pass, but there is no LLM intent-classification fallback for unfamiliar campus phrasing.
- LLM-backed chat remains slow at 8–33 seconds in this local environment.
- Streaming does not automatically reconnect after a disconnect.
- Agent sessions are held in an in-memory deque and are lost when the API process restarts.
- The frontend has no automated test suite. Rendered UI, browser console and screenshots could not be verified during this audit.
- Voice assistant functionality is not implemented.
- Campus records are synthetic sample data; official policies, schedules and dates are not connected.
