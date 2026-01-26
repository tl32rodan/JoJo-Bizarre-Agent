from __future__ import annotations

from app.config import EmbeddingConfig
from app.core.embeddings import RemoteEmbeddingModel


def test_remote_embedding_model_batches(monkeypatch) -> None:
    def fake_post_json(self, url, payload, timeout):
        if payload["input"] == "ping":
            return {"embeddings": [[0.1, 0.2, 0.3]]}
        return {"embeddings": [[0.0, 0.0, 1.0] for _ in payload["input"]]}

    monkeypatch.setattr(RemoteEmbeddingModel, "_post_json", fake_post_json)

    config = EmbeddingConfig(host="host", model="model", batch_size=2, max_workers=1)
    model = RemoteEmbeddingModel(config=config)

    embeddings = model.encode(["a", "b", "c"])

    assert len(embeddings) == 3
    assert embeddings[0] == [0.0, 0.0, 1.0]


def test_remote_embedding_model_error_returns_zero(monkeypatch) -> None:
    def fake_post_json(self, url, payload, timeout):
        if payload["input"] == "ping":
            return {"embeddings": [[0.1, 0.2]]}
        raise RuntimeError("boom")

    monkeypatch.setattr(RemoteEmbeddingModel, "_post_json", fake_post_json)

    config = EmbeddingConfig(host="host", model="model", batch_size=2, max_workers=1)
    model = RemoteEmbeddingModel(config=config)

    embeddings = model.encode(["a", "b"])

    assert embeddings == [[0.0, 0.0], [0.0, 0.0]]
