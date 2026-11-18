import re

from backend.app.config import get_settings
from backend.app.rag.vector_store import get_collection, get_embedding_model


def normalize_query(question: str) -> str:
    """Correct common campus-query spelling variants without altering stored/displayed text."""
    normalized = question
    normalized = re.sub(r"\battendence\b", "attendance", normalized, flags=re.IGNORECASE)
    return normalized


def search_faq(question: str, top_k: int = 4) -> dict:
    collection = get_collection()
    if collection.count() == 0:
        return {"found": False, "results": [], "message": "FAQ knowledge base is empty. Run the ingestion command."}
    normalized = normalize_query(question)
    if re.search(r"\battendance\b", normalized, re.I) and re.search(r"\b(minimum|requirement|required|needed|policy|criteria|eligible|eligibility|percentage|percent|shortage|condonation|rules?|for exams?|end[- ]semester)\b", normalized, re.I):
        normalized = "minimum attendance requirement"
    vector = get_embedding_model().encode([normalized], normalize_embeddings=True).tolist()
    result = collection.query(query_embeddings=vector, n_results=min(top_k, collection.count()), include=["documents", "metadatas", "distances"])
    hits = []
    for document_id, doc, metadata, distance in zip(result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]):
        relevance = max(0.0, 1.0 - float(distance))
        if relevance >= get_settings().faq_relevance_threshold:
            hits.append({"document_title": metadata["source"], "source_filename": metadata["source"], "category": metadata["category"], "passage": doc, "retrieved_content": doc, "source_id": metadata["faq_id"], "document_id": document_id, "retrieval_score": round(relevance, 4), "relevance_score": round(relevance, 4), "distance": round(float(distance), 4), "score_type": "1 - cosine distance (higher is more relevant)", "metadata": metadata, "text": doc, "source": metadata["source"], "faq_id": metadata["faq_id"], "last_updated": metadata["last_updated"], "relevance": round(relevance, 4)})
    return {"found": bool(hits), "results": hits, "message": "" if hits else "No sufficiently relevant FAQ records were found."}
