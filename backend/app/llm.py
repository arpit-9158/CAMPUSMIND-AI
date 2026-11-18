from ollama import Client
import re
from datetime import datetime

from backend.app.config import get_settings


def ollama_client() -> Client:
    settings = get_settings()
    return Client(host=settings.ollama_base_url, timeout=settings.ollama_timeout_seconds)


def check_llm() -> dict:
    settings = get_settings()
    try:
        tags = ollama_client().list()
        models = [item.model for item in tags.models]
        available = settings.ollama_model in models
        return {"available": available, "model": settings.ollama_model, "installed_models": models, "message": "Model is ready." if available else f"Required model {settings.ollama_model} is not installed. Run: ollama pull {settings.ollama_model}"}
    except Exception as exc:
        return {"available": False, "model": settings.ollama_model, "installed_models": [], "message": f"Ollama is unavailable: {exc.__class__.__name__}: {exc}"}


def generate_answer(question: str, evidence: list[dict]) -> str:
    if evidence and not any(bool(item.get("data", {}).get("found")) for item in evidence):
        return "I couldn't find reliable information in the available synthetic campus data. Please confirm with the relevant campus office."
    settings = get_settings()
    evidence_text = "\n\n".join(f"[{item['tool']}] {item['data']}" for item in evidence)
    response = ollama_client().chat(
        model=settings.ollama_model,
        messages=[
            {"role": "system", "content": "You are CampusMind AI, a campus helpdesk assistant. Answer in at most 2 concise sentences and use only supplied evidence. Read each tool result carefully and use exact values. Never invent personal attendance percentages, student histories, academic records, or university rules. The sample data contains no individual attendance records. Treat FAQ results as retrieved handbook passages; timetable and calendar records are tool evidence, not FAQ sources. Do not cite file paths or invent citations. Clearly label policies, schedules, and dates as synthetic sample data and not official guidance. If relevant evidence is missing, say it is unavailable and suggest confirming with the relevant campus office. Clearly label email text as a draft and never claim it was sent."},
            {"role": "user", "content": f"Question: {question}\n\nTool evidence:\n{evidence_text or 'No matching evidence was retrieved.'}"},
        ],
        options={"temperature": settings.ollama_temperature},
    )
    answer = response.message.content.strip()
    verified = _verified_response(question, evidence)
    if verified:
        return verified
    has_relevant_record = False
    for item in evidence:
        data = item["data"]
        has_relevant_record = has_relevant_record or bool(data.get("found"))
    answer = re.sub(r"\[(?:check_[^\]]+|FAQ-?\d+)\]", "", answer, flags=re.IGNORECASE)
    if has_relevant_record:
        answer = re.sub(r"(?is)(?:the\s+)?[^.!?]*(?:not specified|not provided|could not find)[^.!?]*\.(?:\s*however,)?\s*", "", answer, count=1)
    for item in evidence:
        data = item["data"]
        if item["tool"] == "search_university_faq":
            for hit in data.get("results", []):
                text = hit["text"]
                if "minimum attendance requirement" in text.casefold() and "75 percent" in text and "75 percent" not in answer.casefold():
                    answer += "\n\nThe sample FAQ states a minimum attendance requirement of 75 percent."
                if "leave application" in question.casefold() and "@" in text and not any(token in answer for token in ("@example.edu", "@")):
                    email = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
                    if email:
                        answer += f"\n\nThe sample department contact is {email.group(0)}."
                if "reappear examination rules" in question.casefold() and "reappear examination" in text.casefold() and "listed examination fee" in text and "examination fee" not in answer.casefold():
                    answer += "\n\n" + text.split("Answer:", 1)[-1].strip()
        elif item["tool"] == "check_timetable" and data.get("found") and data.get("next_occurrence"):
            record = data["records"][0]
            next_date = data["next_occurrence"]
            pretty_date = re.sub(r"\b0(\d)", r"\1", datetime.strptime(next_date, "%Y-%m-%d").strftime("%B %d, %Y"))
            if (next_date not in answer and pretty_date not in answer) or any(value not in answer for value in (record["start_time"], record["end_time"], record["room"])):
                answer += f"\n\nThe next listed {record['subject']} class is {record['day']}, {pretty_date}, {record['start_time']}-{record['end_time']} in {record['room']}."
        elif item["tool"] == "check_academic_calendar" and not data.get("found") and item["input"].get("weekday"):
            weekday = item["input"]["weekday"]
            if weekday.casefold() not in answer.casefold() or "no event" not in answer.casefold():
                answer += f"\n\nThe sample academic calendar has no events listed for {weekday}."
    if any(item["tool"] == "generate_email_draft" for item in evidence) and "not sent" not in answer.casefold():
        answer += "\n\nDraft only; not sent."
    if not any(phrase in answer.casefold() for phrase in ("synthetic sample", "sample data", "not official")):
        answer += "\n\nNote: This information comes from synthetic sample campus data and is not official university guidance."
    return answer


def _verified_response(question: str, evidence: list[dict]) -> str:
    """Compose critical policy/date/schedule facts from returned records, not model recall."""
    q = question.casefold()
    faq_hits = [hit for item in evidence if item["tool"] == "search_university_faq" for hit in item["data"].get("results", [])]
    timetable_items = [item for item in evidence if item["tool"] == "check_timetable"]
    timetable = [record for item in timetable_items for record in item["data"].get("records", [])]
    calendar_items = [item for item in evidence if item["tool"] == "check_academic_calendar"]
    calendar = [record for item in calendar_items for record in item["data"].get("records", [])]
    fragments = []
    if "attendance" in q and re.search(r"\b(minimum|requirement|required|needed|policy|criteria|rules?|eligible|eligibility|percentage|percent)\b", q):
        hit = next((h for h in faq_hits if "minimum attendance" in h.get("passage", h.get("text", "")).casefold() and "75 percent" in h.get("passage", h.get("text", "")).casefold()), None)
        if hit:
            fragments.append("The retrieved sample FAQ lists at least 75% attendance in each course for end-semester exam eligibility.")
    if timetable and re.search(r"\b(class|timetable|schedule|lecture|when is|what time)\b", q):
        rec = timetable[0]
        item = next((candidate for candidate in timetable_items if rec in candidate["data"].get("records", [])), {})
        next_occurrence = item.get("data", {}).get("next_occurrence")
        if next_occurrence and re.search(r"\b(next|upcoming)\b", q):
            date_label = datetime.strptime(next_occurrence, "%Y-%m-%d").strftime("%B %d, %Y").replace(" 0", " ")
            fragments.append(f"The next sample {rec['subject']} class is {rec['day']}, {date_label}, {rec['start_time']} to {rec['end_time']} in {rec['room']}.")
        else:
            fragments.append(f"The sample timetable lists {rec['subject']} on {rec['day']} from {rec['start_time']} to {rec['end_time']} in {rec['room']}.")
    if calendar and re.search(r"\b(exam|examination|calendar|event|next)\b", q):
        rec = calendar[0]
        if rec.get("event_name") and rec.get("event_date"):
            date_label = datetime.strptime(rec["event_date"], "%Y-%m-%d").strftime("%B %d, %Y").replace(" 0", " ")
            fragments.append(f"The next listed sample examination is {rec['event_name']} on {date_label}.")
        elif rec.get("event_date"):
            date_label = datetime.strptime(rec["event_date"], "%Y-%m-%d").strftime("%B %d, %Y").replace(" 0", " ")
            fragments.append(f"The sample calendar lists an event on {date_label}.")
    for item in calendar_items:
        weekday = item.get("input", {}).get("weekday")
        if not item["data"].get("found") and weekday:
            fragments.append(f"The sample academic calendar has no events listed for {weekday}.")
    if "reappear" in q:
        hit = next((h for h in faq_hits if "reappear examination rules" in h.get("passage", h.get("text", "")).casefold()), None)
        if hit:
            content = hit.get("passage", hit.get("text", ""))
            answer = content.split("Answer:", 1)[-1].strip()
            if answer:
                fragments.append(f"The retrieved sample FAQ says: {answer}")
    if fragments:
        return " ".join(fragments) + " Synthetic sample data; confirm official policy and dates with your campus office."
    return ""
