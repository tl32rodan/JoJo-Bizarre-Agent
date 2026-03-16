"""Shared test fixtures for react_agent tests."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

# Ensure both repo root and src/ are on the path.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_SRC = ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------

class FakeLLMResponse:
    """Simulates a LangChain AIMessage."""

    def __init__(self, content: str = "", tool_calls: list | None = None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.additional_kwargs: dict[str, Any] = {}


class FakeLLM:
    """Controllable mock LLM client."""

    def __init__(self, responses: list[FakeLLMResponse] | None = None):
        self._responses = list(responses or [])
        self._call_count = 0
        self.invocations: list[list[dict[str, Any]]] = []

    def invoke(self, messages: list[dict[str, Any]]) -> FakeLLMResponse:
        self.invocations.append(messages)
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
            self._call_count += 1
            return resp
        return FakeLLMResponse(content="Default answer.")

    def bind_tools(self, tools: list[Any]) -> "FakeLLM":
        return self


@pytest.fixture
def mock_llm():
    return FakeLLM


@pytest.fixture
def fake_llm_response():
    return FakeLLMResponse


# ---------------------------------------------------------------------------
# Mock Embedding
# ---------------------------------------------------------------------------

class FakeEmbedding:
    """Returns deterministic vectors based on text hash."""

    def __init__(self, dimension: int = 8):
        self.dimension = dimension

    def get_text_embedding(self, text: str) -> list[float]:
        h = hash(text) % (10**6)
        return [(h + i) % 100 / 100.0 for i in range(self.dimension)]

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [self.get_text_embedding(t) for t in texts]

    def get_sentence_embedding_dimension(self) -> int:
        return self.dimension


@pytest.fixture
def mock_embedding():
    return FakeEmbedding()


# ---------------------------------------------------------------------------
# Mock Vector Store
# ---------------------------------------------------------------------------

class FakeVectorStore:
    """In-memory vector store matching SMAK's interface."""

    def __init__(self):
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


@pytest.fixture
def mock_vector_store():
    return FakeVectorStore()


# ---------------------------------------------------------------------------
# Mock Query Service
# ---------------------------------------------------------------------------

class FakeQueryService:
    def __init__(self, hits=None, related=None):
        self._hits = hits or []
        self._related = related or []

    def search(self, text: str, top_k: int = 5) -> dict[str, list[dict[str, Any]]]:
        return {"hits": self._hits[:top_k], "related_context": self._related}


@pytest.fixture
def mock_query_service():
    return FakeQueryService
