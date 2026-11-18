# CampusMind AI Project Report

## Problem and objective

Campus questions often require combining handbook policies, class schedules, and academic dates. CampusMind AI demonstrates a local helpdesk that retrieves sample policy documents and joins them with actual schedule/calendar JSON records.

## Scope

This is an academic demonstration using synthetic, explicitly labelled campus policies and schedules. It is not affiliated with a real university, does not authenticate users, does not access student records, and does not send email.

## Components

- Data layer: 40 CSV FAQ records and JSON timetable/calendar datasets.
- Retrieval: Sentence Transformers, chunking, persistent ChromaDB, source metadata.
- Orchestration: LangGraph state graph, intent-based tool routing, actual tool calls, Ollama answer synthesis.
- Service: FastAPI endpoints with request validation and structured failures.
- Interface: React/Vite dashboard consuming API responses for chat, schedule, dates, FAQ records, activity, and settings.

## DoD status

Implementation and execution evidence are tracked in `TESTING_REPORT.md`. Completion is asserted only for items verified by actual commands and recorded output.
