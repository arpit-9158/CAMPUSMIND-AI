# CampusMind AI Architecture

## Request path

The React + TypeScript client reads dashboard data from the health, stats, timetable, calendar, FAQ, and activity APIs. Chat submits to `POST /chat/stream`; actual LangGraph execution events arrive as SSE and the final answer includes tool results and retrieved FAQ documents. `POST /chat` remains available for non-streaming clients. Session events are available at `GET /agent/activity/{session_id}` and recent sessions at `/activity`.

LangGraph nodes:

1. **Plan:** deterministic intent routing selects matching tools and records the selected tool names. Each tool is included only for relevant query cues.
2. **Execute:** calls FAQ, timetable, calendar, and/or email draft functions; records start/completion/failure timestamps, duration, and safe result summaries. Tool failures use generic user-facing details.
3. **Compose:** sends only tool evidence and the original question to the exact configured Ollama model. Verified critical attendance, schedule, and exam facts are composed from returned records. The system prompt forbids unsupported policies, schedules, personal attendance claims, and sent-email claims. On model failure, the agent composes a concise response from returned evidence.

No hidden chain-of-thought is returned. Observable execution events describe tool activity only.

## Data and RAG

The FAQ CSV has a strict required schema and date validation. Text is whitespace-cleaned, formatted as question/answer documents, split with `RecursiveCharacterTextSplitter`, embedded using Sentence Transformers `all-MiniLM-L6-v2`, normalized, then upserted with category, source, FAQ ID, and update date metadata into a persistent ChromaDB collection. Retrieval returns the Chroma document ID, source FAQ ID, title, category, retrieved passage, metadata, cosine distance, and `1 - distance` relevance score. These FAQ citations are kept separate from timetable/calendar tool evidence. The timetable/calendar readers parse and validate the actual JSON records on every call.

## Dashboard and activity UI

The Dashboard combines live `/stats`, `/health`, `/health/llm`, `/timetable`, `/calendar`, and `/activity` responses. It derives record counts and previews from API results. The Agent Activity page polls recent completed sessions and displays timestamped event summaries; the assistant consumes SSE to reflect events during the live run. No hidden model reasoning is sent to the UI.

## Failure handling

The API reports Ollama readiness separately. Unknown/missing records remain explicit no-result values. Data parse failures produce structured service errors. Chat tool execution records failures; LLM unavailability triggers the evidence-only fallback. No calls are made to external university systems or email services.
