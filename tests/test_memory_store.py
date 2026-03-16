"""Tests for react_agent.memory.store."""

from __future__ import annotations

import pytest

from react_agent.memory.store import MemoryStore, MemoryConfig, MemoryEntry
from conftest import FakeEmbedding, FakeVectorStore, FakeQueryService


class TestMemoryStoreStandalone:
    """Test MemoryStore without SMAK QueryService (standalone mode)."""

    def test_store_and_recall(self, mock_vector_store, mock_embedding):
        store = MemoryStore(vector_store=mock_vector_store, embedder=mock_embedding)
        uid = store.store("Python is great", {"type": "fact"})
        assert uid  # non-empty
        results = store.recall("Python")
        assert len(results) >= 1
        assert results[0].content == "Python is great"

    def test_recall_empty_store(self, mock_embedding):
        vs = FakeVectorStore()
        store = MemoryStore(vector_store=vs, embedder=mock_embedding)
        results = store.recall("anything")
        assert results == []

    def test_store_fact(self, mock_vector_store, mock_embedding):
        store = MemoryStore(vector_store=mock_vector_store, embedder=mock_embedding)
        store.store_fact("FAISS uses L2 distance", source="docs")
        results = store.recall("FAISS")
        assert len(results) == 1
        assert results[0].metadata.get("type") == "fact"

    def test_store_preference(self, mock_vector_store, mock_embedding):
        store = MemoryStore(vector_store=mock_vector_store, embedder=mock_embedding)
        store.store_preference("language", "zh-TW")
        results = store.recall("language")
        assert len(results) == 1
        assert results[0].metadata.get("type") == "preference"
        assert results[0].metadata.get("key") == "language"

    def test_persist_called_on_store(self, mock_vector_store, mock_embedding):
        store = MemoryStore(vector_store=mock_vector_store, embedder=mock_embedding)
        store.store("some knowledge")
        assert mock_vector_store.persist_count == 1

    def test_metadata_preserved(self, mock_vector_store, mock_embedding):
        store = MemoryStore(vector_store=mock_vector_store, embedder=mock_embedding)
        store.store("test content", {"type": "instruction", "custom": "value"})
        results = store.recall("test")
        assert results[0].metadata.get("type") == "instruction"
        assert results[0].metadata.get("custom") == "value"
        assert "timestamp" in results[0].metadata


class TestMemoryStoreWithQueryService:
    """Test MemoryStore with SMAK QueryService (includes relation expansion)."""

    def test_recall_uses_query_service(self, mock_vector_store, mock_embedding):
        qs = FakeQueryService(
            hits=[{
                "uid": "h1", "content": "Hit 1", "metadata": {"type": "fact"},
                "score": 0.9, "match_type": "semantic",
            }],
            related=[{
                "uid": "r1", "content": "Related 1", "source_hit": "h1",
                "match_type": "relation",
            }],
        )
        store = MemoryStore(
            vector_store=mock_vector_store, embedder=mock_embedding,
            query_service=qs,
        )
        results = store.recall("query")
        assert len(results) == 2
        assert results[0].match_type == "semantic"
        assert results[1].match_type == "relation"
