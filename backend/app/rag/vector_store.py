from functools import lru_cache

import chromadb
from sentence_transformers import SentenceTransformer

from backend.app.config import get_settings


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(get_settings().embedding_model)


def get_collection():
    settings = get_settings()
    path = settings.path(settings.chroma_path)
    path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(path))
    return client.get_or_create_collection(
        name=settings.chroma_collection,
        metadata={"hnsw:space": "cosine", "description": "CampusMind synthetic university FAQ chunks"},
    )
