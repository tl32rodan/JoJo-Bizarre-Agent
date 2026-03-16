"""Shared test fixtures for react_agent tests."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

# Ensure src/ is on the path so ``import react_agent`` works in tests.
ROOT = Path(__file__).resolve().parents[1]
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
# Re-export fallback stubs used by several test modules
# ---------------------------------------------------------------------------

from react_agent.memory.fallback import FallbackEmbedding as FakeEmbedding  # noqa: E402
from react_agent.memory.fallback import FallbackVectorStore as FakeVectorStore  # noqa: E402


@pytest.fixture
def mock_embedding():
    return FakeEmbedding()


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
