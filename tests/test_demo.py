from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import demo


@dataclass
class FakeMessage:
    content: str


@dataclass
class FakeChoice:
    message: FakeMessage


@dataclass
class FakeResponse:
    choices: list[FakeChoice]


class FakeCompletions:
    def create(self, *, model, messages, temperature):
        return FakeResponse(choices=[FakeChoice(message=FakeMessage(content="ok"))])


class FakeChat:
    completions = FakeCompletions()


class FakeClient:
    chat = FakeChat()


class FakeOpenAI:
    def OpenAI(self):
        return FakeClient()


def test_initialize_search_engine_raises(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    try:
        demo.initialize_search_engine(str(missing))
    except FileNotFoundError as exc:
        assert "Index not found" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError")


def test_search_engine_search(tmp_path: Path) -> None:
    path = tmp_path / "index"
    path.touch()
    engine = demo.initialize_search_engine(str(path))

    result = engine.search("query")

    assert "query" in result


def test_openai_client_adapter_invoke() -> None:
    adapter = demo.OpenAIClientAdapter(FakeClient(), model="model")

    assert adapter.invoke("hi") == "ok"


def test_build_llm_client(monkeypatch) -> None:
    monkeypatch.setattr(demo.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(demo.importlib, "import_module", lambda name: FakeOpenAI())

    client = demo.build_llm_client("model")

    assert isinstance(client, demo.OpenAIClientAdapter)
