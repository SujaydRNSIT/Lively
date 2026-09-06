import logging
from typing import List, Dict, Any, Optional
from app.db.vector_store import vector_store
from app.scripts.ingest_docs import run_ingestion

logger = logging.getLogger("lively.core.rag")

class RAGCore:
    """
    Task 7.2:
    Retrieves grounded context for product/pricing/availability turns.
    Instructs the LLM to ground factual claims strictly in retrieved context.
    """
    def __init__(self):
        run_ingestion()

    def retrieve(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        return vector_store.search(query, top_k=top_k)

    def format_grounding_context(self, query: str) -> str:
        hits = self.retrieve(query, top_k=2)
        if not hits:
            return "No specific battlecard snippet found."
        
        formatted = []
        for h in hits:
            formatted.append(f"[{h['title']} - Category: {h['category']}]\n{h['content']}")
        
        return "\n\n".join(formatted)

rag_core = RAGCore()
