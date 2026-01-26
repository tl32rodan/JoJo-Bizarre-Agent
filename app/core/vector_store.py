from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Protocol, Sequence


@dataclass(frozen=True)
class Document:
    path: str
    content: str


class KnowledgeStore(Protocol):
    def load_documents(self) -> Sequence[Document]:
        ...


class EmbeddingModel(Protocol):
    def encode(self, texts: List[str]) -> List[List[float]]:
        ...


@dataclass
class FaissManager:
    dimension: int

    def __post_init__(self) -> None:
        self._documents: List[Document] = []
        self._embeddings: List[List[float]] = []

    def index_from_store(self, store: KnowledgeStore, embedding_model: EmbeddingModel) -> None:
        documents = list(store.load_documents())
        if not documents:
            self._documents = []
            self._embeddings = []
            return
        embeddings = embedding_model.encode([doc.content for doc in documents])
        if len(embeddings) != len(documents):
            raise ValueError("Embedding/documents count mismatch.")
        self._documents = documents
        self._embeddings = embeddings

    def search(
        self,
        query: str,
        *,
        embedding_model: EmbeddingModel,
        top_k: int = 5,
    ) -> List[Document]:
        if not self._documents:
            return []
        query_embedding = embedding_model.encode([query])[0]
        scores = [
            (self._cosine_similarity(query_embedding, emb), doc)
            for doc, emb in zip(self._documents, self._embeddings)
        ]
        scores.sort(key=lambda pair: pair[0], reverse=True)
        return [doc for _, doc in scores[:top_k]]

    def save_local(self, path: str) -> None:
        payload = {
            "dimension": self.dimension,
            "documents": [doc.__dict__ for doc in self._documents],
            "embeddings": self._embeddings,
        }
        Path(path).write_text(json.dumps(payload), encoding="utf-8")

    def load_local(self, path: str) -> bool:
        storage = Path(path)
        if not storage.exists():
            return False
        payload = json.loads(storage.read_text(encoding="utf-8"))
        self.dimension = payload.get("dimension", self.dimension)
        self._documents = [Document(**doc) for doc in payload.get("documents", [])]
        self._embeddings = payload.get("embeddings", [])
        return True

    @staticmethod
    def _cosine_similarity(vec_a: Iterable[float], vec_b: Iterable[float]) -> float:
        dot = 0.0
        norm_a = 0.0
        norm_b = 0.0
        for a, b in zip(vec_a, vec_b):
            dot += a * b
            norm_a += a * a
            norm_b += b * b
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / ((norm_a**0.5) * (norm_b**0.5))
