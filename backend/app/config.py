from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "CampusMind AI"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_timeout_seconds: int = 120
    ollama_temperature: float = 0.1
    faq_csv_path: str = "backend/data/faq.csv"
    timetable_json_path: str = "backend/data/timetable.json"
    calendar_json_path: str = "backend/data/academic_calendar.json"
    chroma_path: str = "backend/chroma_db"
    chroma_collection: str = "campus_faq"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    faq_relevance_threshold: float = 0.60
    frontend_origin: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    def path(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else ROOT / path


@lru_cache
def get_settings() -> Settings:
    return Settings()
