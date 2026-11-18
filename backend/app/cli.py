import argparse
import json

from backend.app.agents.graph import run_agent
from backend.app.config import get_settings
from backend.app.data import load_calendar, load_faq_csv, load_timetable
from backend.app.rag.ingestion import ingest_faq
from backend.app.rag.retriever import search_faq


def main() -> None:
    parser = argparse.ArgumentParser(description="CampusMind AI local data and query commands")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="Load, validate, embed, and persist FAQ chunks")
    ingest.add_argument("--rebuild", action="store_true", help="Safely replace all existing FAQ chunks")
    commands.add_parser("validate", help="Validate FAQ CSV and JSON datasets")
    query = commands.add_parser("ask", help="Run a query through the multi-tool agent")
    query.add_argument("question", nargs="+")
    args = parser.parse_args()
    settings = get_settings()
    if args.command == "ingest":
        result = ingest_faq(rebuild=args.rebuild)
    elif args.command == "validate":
        result = {"faq_records": len(load_faq_csv(settings.path(settings.faq_csv_path))), "timetable_records": len(load_timetable(settings.path(settings.timetable_json_path))), "calendar_events": len(load_calendar(settings.path(settings.calendar_json_path))), "valid": True}
    else:
        result = run_agent(" ".join(args.question))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
