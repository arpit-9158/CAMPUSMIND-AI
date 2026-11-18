from backend.app.rag.retriever import search_faq
from backend.app.rag.vector_store import get_collection
from langchain_text_splitters import RecursiveCharacterTextSplitter


def test_recursive_chunking_preserves_document_text():
    text = "Campus handbook information. " * 90
    chunks = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=20).split_text(text)
    assert len(chunks) > 1
    assert all(len(chunk) <= 220 for chunk in chunks)


def test_chromadb_persistent_collection_is_populated():
    assert get_collection().count() >= 40


def test_rag_returns_grounded_attendance_source():
    result = search_faq("minimum attendance requirement")
    assert result["found"]
    assert any("75 percent" in item["text"] for item in result["results"])
    assert any(item["source"] == "Sample Student Handbook 2026" for item in result["results"])
    hit = result["results"][0]
    assert hit["source_id"].startswith("faq-")
    assert hit["document_id"].startswith("faq-")
    assert hit["retrieved_content"] == hit["passage"]
    assert hit["relevance_score"] == hit["retrieval_score"]
    assert hit["distance"] >= 0
