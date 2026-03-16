"""Agent memory store backed by SMAK's vector search infrastructure."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol


class EmbeddingModel(Protocol):
    """Minimal embedding interface compatible with SMAK's InternalNomicEmbedding."""

    def get_text_embedding(self, text: str) -> list[float]: ...


class VectorStore(Protocol):
    """Minimal vector store interface compatible with SMAK's FaissVectorStore."""

    def add(self, nodes: list[Any]) -> None: ...
    def search(self, query_vector: list[float], top_k: int = 5) -> list[dict[str, Any]]: ...
    def get_by_id(self, uid: str) -> dict[str, Any] | None: ...
    def persist(self) -> None: ...


class QueryServiceLike(Protocol):
    """Minimal interface matching SMAK QueryService.search()."""

    def search(self, text: str, top_k: int = 5) -> dict[str, list[dict[str, Any]]]: ...


@dataclass(frozen=True)
class MemoryEntry:
    uid: str
    content: str
    metadata: dict[str, Any]
    score: float | None = None
    match_type: str = "semantic"


@dataclass(frozen=True)
class MemoryConfig:
    index_name: str = "agent_memory"
    storage_dir: str = "./agent_data/memory"
    max_entries: int = 10000
    auto_memorize: bool = True


class MemoryStore:
    """Long-term knowledge store using SMAK-compatible vector search.

    Supports two modes:
    1. Full SMAK mode: Backed by SMAK QueryService (with 1-hop relation expansion).
    2. Standalone mode: Backed by any VectorStore + EmbeddingModel.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        embedder: EmbeddingModel,
        query_service: QueryServiceLike | None = None,
        config: MemoryConfig | None = None,
    ) -> None:
        self._vector_store = vector_store
        self._embedder = embedder
        self._query_service = query_service
        self._config = config or MemoryConfig()

    def recall(self, query: str, top_k: int = 5) -> list[MemoryEntry]:
        """Semantic search over stored memories.

        Uses SMAK QueryService (with relation expansion) if available,
        otherwise falls back to direct vector search.
        """
        if self._query_service is not None:
            return self._recall_via_query_service(query, top_k)
        return self._recall_via_vector_store(query, top_k)

    def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """Store a piece of knowledge. Returns the generated UID."""
        uid = uuid.uuid4().hex[:16]
        meta = {
            "timestamp": time.time(),
            "type": "general",
            **(metadata or {}),
        }
        vector = self._embedder.get_text_embedding(content)
        node = _MemoryNode(uid=uid, content=content, metadata=meta, vector=vector)
        self._vector_store.add([node])
        self._vector_store.persist()
        return uid

    def store_fact(self, fact: str, source: str = "") -> str:
        """Store a factual piece of knowledge."""
        return self.store(fact, {"type": "fact", "source": source})

    def store_preference(self, key: str, value: str) -> str:
        """Store a user preference."""
        return self.store(
            f"{key}: {value}",
            {"type": "preference", "key": key, "value": value},
        )

    def persist(self) -> None:
        """Flush to disk."""
        self._vector_store.persist()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _recall_via_query_service(self, query: str, top_k: int) -> list[MemoryEntry]:
        result = self._query_service.search(query, top_k=top_k)  # type: ignore[union-attr]
        entries: list[MemoryEntry] = []
        for hit in result.get("hits", []):
            entries.append(MemoryEntry(
                uid=hit.get("uid", ""),
                content=hit.get("content", ""),
                metadata=hit.get("metadata", {}),
                score=hit.get("score"),
                match_type=hit.get("match_type", "semantic"),
            ))
        for rel in result.get("related_context", []):
            entries.append(MemoryEntry(
                uid=rel.get("uid", ""),
                content=rel.get("content", ""),
                metadata={},
                match_type="relation",
            ))
        return entries

    def _recall_via_vector_store(self, query: str, top_k: int) -> list[MemoryEntry]:
        query_vec = self._embedder.get_text_embedding(query)
        results = self._vector_store.search(query_vec, top_k=top_k)
        entries: list[MemoryEntry] = []
        for hit in results:
            if not isinstance(hit, dict):
                continue
            entries.append(MemoryEntry(
                uid=hit.get("uid", ""),
                content=hit.get("content", ""),
                metadata=hit.get("metadata", {}),
                score=hit.get("score"),
            ))
        return entries


@dataclass
class _MemoryNode:
    """Mimics llama-index TextNode interface expected by SMAK's vector store."""
    uid: str
    content: str
    metadata: dict[str, Any]
    vector: list[float]

    @property
    def id_(self) -> str:
        return self.uid

    @property
    def text(self) -> str:
        return self.content

    @property
    def embedding(self) -> list[float]:
        return self.vector

    @embedding.setter
    def embedding(self, value: list[float]) -> None:
        self.vector = value

    def get_content(self) -> str:
        return self.content
