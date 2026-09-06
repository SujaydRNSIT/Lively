import logging
from typing import List, Dict, Any

from app.config import settings

logger = logging.getLogger("lively.db.vector_store")

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


class PineconeVectorStore:
    """Pinecone-backed vector store with local sentence-transformer embeddings."""

    def __init__(self):
        self._pc = None
        self._index = None
        self._encoder = None
        self._namespace = settings.PINECONE_NAMESPACE
        self._index_name = settings.PINECONE_INDEX_NAME
        self._initialized = False
        self._fallback_docs: List[Dict[str, Any]] = []

    def _ensure_init(self):
        if self._initialized:
            return
        self._initialized = True

        if not settings.PINECONE_API_KEY:
            logger.warning("PINECONE_API_KEY not set — falling back to in-memory keyword search")
            return

        try:
            from pinecone import Pinecone, ServerlessSpec
            from sentence_transformers import SentenceTransformer

            self._pc = Pinecone(api_key=settings.PINECONE_API_KEY)
            existing = [idx.name for idx in self._pc.list_indexes()]
            if self._index_name not in existing:
                self._pc.create_index(
                    name=self._index_name,
                    dimension=EMBEDDING_DIM,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
                )
            self._index = self._pc.Index(self._index_name)
            # Force device="cpu" to prevent CUDA kernel mismatches on newer GPUs (e.g. RTX 50-series)
            self._encoder = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
            logger.info(f"Pinecone index '{self._index_name}' ready ({EMBEDDING_DIM}d, cosine) using CPU encoder")
        except Exception as e:
            logger.warning(f"Failed to initialize Pinecone/SentenceTransformer ({e}). Falling back to in-memory store.")
            self._index = None
            self._encoder = None

    def _embed(self, text: str) -> List[float]:
        if not self._encoder:
            return []
        try:
            return self._encoder.encode(text, normalize_embeddings=True, device="cpu").tolist()
        except Exception as e:
            logger.warning(f"Embedding error on CPU: {e}")
            return []

    def _fallback_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Keyword fallback when Pinecone is not configured."""
        query_terms = set(query.lower().split())
        scored = []
        for doc in self._fallback_docs:
            score = 0.0
            for kw in doc.get("keywords", []):
                if kw.lower() in query.lower():
                    score += 3.0
                elif any(qt in kw.lower() for qt in query_terms):
                    score += 1.5
            content_words = set(doc["content"].lower().split())
            score += len(query_terms.intersection(content_words)) * 0.2
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{k: v for k, v in item[1].items() if k != "keywords"} | {"keywords": item[1].get("keywords", [])} for item in scored[:top_k]]

    def upsert_documents(self, documents: List[Dict[str, Any]]):
        """Upsert a batch of documents into Pinecone."""
        self._ensure_init()
        if self._index is None:
            self._fallback_docs.extend(documents)
            logger.info(f"Stored {len(documents)} docs in-memory (no Pinecone)")
            return

        vectors = []
        for doc in documents:
            text = f"{doc['title']}. {doc['content']}"
            vectors.append({
                "id": doc["doc_id"],
                "values": self._embed(text),
                "metadata": {
                    "title": doc["title"],
                    "category": doc["category"],
                    "content": doc["content"],
                    "keywords": ",".join(doc.get("keywords", [])),
                },
            })
        self._index.upsert(vectors=vectors, namespace=self._namespace)
        logger.info(f"Upserted {len(vectors)} documents to Pinecone index '{self._index_name}'")

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Semantic search via Pinecone. Returns list of doc dicts."""
        self._ensure_init()
        if self._index is None:
            return self._fallback_search(query, top_k)

        query_vec = self._embed(query)
        results = self._index.query(
            vector=query_vec,
            top_k=top_k,
            namespace=self._namespace,
            include_metadata=True,
        )
        hits = []
        for match in results.get("matches", []):
            meta = match.get("metadata", {})
            hits.append({
                "doc_id": match["id"],
                "title": meta.get("title", ""),
                "category": meta.get("category", ""),
                "content": meta.get("content", ""),
                "keywords": meta.get("keywords", "").split(",") if meta.get("keywords") else [],
                "score": match.get("score", 0.0),
            })
        return hits

    def add_document(self, doc_id: str, title: str, category: str, content: str, keywords: List[str]):
        """Single-doc convenience wrapper."""
        self.upsert_documents([{
            "doc_id": doc_id,
            "title": title,
            "category": category,
            "content": content,
            "keywords": keywords,
        }])


vector_store = PineconeVectorStore()
