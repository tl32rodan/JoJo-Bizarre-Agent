from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from app.core.vector_store import Document, FaissManager


@dataclass
class FakeStore:
    documents: List[Document]

    def load_documents(self) -> List[Document]:
        return self.documents


class FakeEmbedding:
    def __init__(self, mapping):
        self.mapping = mapping

    def encode(self, texts: List[str]) -> List[List[float]]:
        return [self.mapping[text] for text in texts]


def test_faiss_manager_search_top_result() -> None:
    docs = [Document(path="a.py", content="alpha"), Document(path="b.py", content="beta")]
    store = FakeStore(documents=docs)
    embeddings = {"alpha": [1.0, 0.0], "beta": [0.0, 1.0], "query": [1.0, 0.0]}
    model = FakeEmbedding(embeddings)
    manager = FaissManager(dimension=2)

    manager.index_from_store(store, model)
    results = manager.search("query", embedding_model=model, top_k=1)

    assert results[0].path == "a.py"


def test_faiss_manager_save_and_load(tmp_path: Path) -> None:
    docs = [Document(path="a.py", content="alpha")]
    store = FakeStore(documents=docs)
    embeddings = {"alpha": [1.0, 0.0], "query": [1.0, 0.0]}
    model = FakeEmbedding(embeddings)
    manager = FaissManager(dimension=2)
    manager.index_from_store(store, model)

    storage = tmp_path / "store.json"
    manager.save_local(str(storage))

    new_manager = FaissManager(dimension=1)
    assert new_manager.load_local(str(storage)) is True
    results = new_manager.search("query", embedding_model=model, top_k=1)

    assert results[0].content == "alpha"
