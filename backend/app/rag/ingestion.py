from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.app.config import get_settings
from backend.app.data import load_faq_csv
from backend.app.rag.vector_store import get_collection, get_embedding_model


def ingest_faq(rebuild: bool = False) -> dict[str, int | str | bool]:
    settings = get_settings()
    rows = load_faq_csv(settings.path(settings.faq_csv_path))
    splitter = RecursiveCharacterTextSplitter(chunk_size=650, chunk_overlap=80, add_start_index=True)
    texts: list[str] = []
    ids: list[str] = []
    metadatas: list[dict[str, str | int]] = []
    for row in rows:
        document = f"Question: {row['question']}\nAnswer: {row['answer']}"
        for index, chunk in enumerate(splitter.split_text(document)):
            texts.append(chunk)
            ids.append(f"{row['id']}-{index}")
            metadatas.append({"faq_id": row["id"], "category": row["category"], "source": row["source"], "last_updated": row["last_updated"]})
    collection = get_collection()
    if rebuild:
        existing = collection.get(include=[])
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
    embeddings = get_embedding_model().encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()
    collection.upsert(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)
    return {"records": len(rows), "chunks": len(texts), "collection": settings.chroma_collection, "persisted": True, "rebuild": rebuild}
