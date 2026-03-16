"""Lightweight in-memory fallbacks when SMAK / faiss-storage-lib are not installed."""

from __future__ import annotations

from typing import Any


class FallbackEmbedding:
    """Hash-based deterministic embedding for development / testing."""

    def __init__(self, dimension: int = 8):
        self.dimension = dimension

    def get_text_embedding(self, text: str) -> list[float]:
        h = hash(text) % (10**6)
        return [(h + i) % 100 / 100.0 for i in range(self.dimension)]

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [self.get_text_embedding(t) for t in texts]

    def get_sentence_embedding_dimension(self) -> int:
        return self.dimension


class FallbackVectorStore:
    """Simple dict-backed vector store for development / testing."""

    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Any]] = {}
        self.persist_count = 0

    def add(self, nodes: list[Any]) -> None:
        for node in nodes:
            uid = getattr(node, "id_", None) or getattr(node, "uid", "")
            self._docs[uid] = {
                "uid": uid,
                "content": getattr(node, "text", "") or getattr(node, "content", ""),
                "metadata": getattr(node, "metadata", {}),
                "score": 1.0,
            }

    def search(self, query_vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        return list(self._docs.values())[:top_k]

    def get_by_id(self, uid: str) -> dict[str, Any] | None:
        return self._docs.get(uid)

    def persist(self) -> None:
        self.persist_count += 1
