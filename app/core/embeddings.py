from __future__ import annotations

import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import List, Protocol

from app.config import EmbeddingConfig


class BaseEmbeddingModel(Protocol):
    def encode(self, texts: List[str]) -> List[List[float]]:
        ...

    def get_sentence_embedding_dimension(self) -> int:
        ...


@dataclass
class RemoteEmbeddingModel:
    config: EmbeddingConfig

    def __post_init__(self) -> None:
        self.dimension = self._fetch_dimension()

    def _post_json(self, url: str, payload: dict, timeout: int) -> dict:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _fetch_dimension(self) -> int:
        url = f"http://{self.config.host}/api/embed"
        data = {"model": self.config.model, "input": "ping"}
        try:
            payload = self._post_json(url, data, timeout=10)
            embeddings = payload.get("embeddings", [])
            if not embeddings or not embeddings[0]:
                raise ValueError("Empty embedding.")
            return len(embeddings[0])
        except Exception as exc:
            raise RuntimeError("Could not determine embedding dimension.") from exc

    def encode(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        batches = [
            texts[i : i + self.config.batch_size]
            for i in range(0, len(texts), self.config.batch_size)
        ]
        results: List[List[float]] = []
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            for batch_embeddings in executor.map(self._embed_batch, batches):
                results.extend(batch_embeddings)
        return results

    def _embed_batch(self, batch_texts: List[str]) -> List[List[float]]:
        url = f"http://{self.config.host}/api/embed"
        data = {"model": self.config.model, "input": batch_texts}
        try:
            payload = self._post_json(url, data, timeout=60)
            embeddings = payload.get("embeddings", [])
            if len(embeddings) != len(batch_texts):
                raise ValueError("Batch mismatch.")
            return embeddings
        except Exception:
            return [[0.0] * self.dimension for _ in batch_texts]

    def get_sentence_embedding_dimension(self) -> int:
        return self.dimension
