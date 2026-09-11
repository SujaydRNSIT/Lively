import os
import logging
from typing import List, Dict, Any

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_TORCH", "1")

from app.config import settings

logger = logging.getLogger("lively.db.vector_store")

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


class PineconeVectorStore:
    """Pinecone-backed vector store with lightweight FastEmbed/SentenceTransformer embeddings."""

    def __init__(self):
        self._pc = None
        self._index = None
        self._encoder = None
        self._fast_encoder = None
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

            # Try FastEmbed first (fast ONNX, lightweight, no TF/torch conflicts)
            self._fast_encoder = None
            try:
                from fastembed import TextEmbedding
                self._fast_encoder = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
                logger.info(f"Pinecone index '{self._index_name}' ready ({EMBEDDING_DIM}d, cosine) using FastEmbed")
            except Exception as fe_err:
                logger.info(f"FastEmbed not available ({fe_err}), trying SentenceTransformer")
                try:
                    from sentence_transformers import SentenceTransformer
                    self._encoder = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
                    logger.info(f"Pinecone index '{self._index_name}' ready ({EMBEDDING_DIM}d, cosine) using CPU encoder")
                except Exception as st_err:
                    logger.warning(f"Could not load SentenceTransformer ({st_err}). Using in-memory keyword RAG.")
        except Exception as e:
            logger.warning(f"Failed to initialize Pinecone/Embedding ({e}). Falling back to in-memory store.")
            self._index = None
            self._encoder = None
            self._fast_encoder = None

    def _embed(self, text: str) -> List[float]:
        if getattr(self, "_fast_encoder", None):
            try:
                return list(self._fast_encoder.embed([text]))[0].tolist()
            except Exception as e:
                logger.warning(f"FastEmbed error: {e}")
        if getattr(self, "_encoder", None):
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
        if self._index is None or (not self._fast_encoder and not self._encoder):
            self._fallback_docs.extend(documents)
            logger.info(f"Stored {len(documents)} docs in-memory (no Pinecone)")
            return

        vectors = []
        for doc in documents:
            text = f"{doc['title']}. {doc['content']}"
            vec = self._embed(text)
            if not vec:
                continue
            vectors.append({
                "id": doc["doc_id"],
                "values": vec,
                "metadata": {
                    "title": doc["title"],
                    "category": doc["category"],
                    "content": doc["content"],
                    "keywords": ",".join(doc.get("keywords", [])),
                },
            })
        if vectors:
            self._index.upsert(vectors=vectors, namespace=self._namespace)
            logger.info(f"Upserted {len(vectors)} documents to Pinecone index '{self._index_name}'")

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Semantic search via Pinecone. Returns list of doc dicts."""
        self._ensure_init()
        if self._index is None or (not self._fast_encoder and not self._encoder):
            return self._fallback_search(query, top_k)

        query_vec = self._embed(query)
        if not query_vec:
            return self._fallback_search(query, top_k)

        try:
            results = self._index.query(
                vector=query_vec,
                top_k=top_k,
                namespace=self._namespace,
                include_metadata=True,
            )
            matched = []
            for match in results.get("matches", []):
                meta = match.get("metadata", {})
                matched.append({
                    "doc_id": match["id"],
                    "title": meta.get("title", ""),
                    "category": meta.get("category", ""),
                    "content": meta.get("content", ""),
                    "score": match.get("score", 0.0),
                    "keywords": [k.strip() for k in meta.get("keywords", "").split(",") if k.strip()],
                })
            return matched if matched else self._fallback_search(query, top_k)
        except Exception as e:
            logger.warning(f"Pinecone query failed ({e}); using fallback search")
            return self._fallback_search(query, top_k)


vector_store = PineconeVectorStore()
