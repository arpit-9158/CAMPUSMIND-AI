from backend.app.rag.retriever import search_faq


def search_university_faq(question: str) -> dict:
    """Search persistent, locally embedded sample FAQ documents."""
    return search_faq(question)
