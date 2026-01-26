from pathlib import Path

from app.config import load_config


def test_load_config_reads_env_file(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LLM_BASE_URL=http://example.com\n"
        "LLM_MODEL=test-model\n"
        "LLM_API_KEY=secret\n"
        "EMBEDDING_HOST=embed-host\n"
        "EMBEDDING_MODEL=embed-model\n"
        "EMBEDDING_BATCH_SIZE=16\n"
        "EMBEDDING_MAX_WORKERS=4\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_HOST", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("EMBEDDING_BATCH_SIZE", raising=False)
    monkeypatch.delenv("EMBEDDING_MAX_WORKERS", raising=False)

    config = load_config(env_path=env_file)

    assert config.llm.base_url == "http://example.com"
    assert config.llm.model_name == "test-model"
    assert config.llm.api_key == "secret"
    assert config.embedding.host == "embed-host"
    assert config.embedding.model == "embed-model"
    assert config.embedding.batch_size == 16
    assert config.embedding.max_workers == 4
