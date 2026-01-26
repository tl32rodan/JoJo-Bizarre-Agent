from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_LLM_BASE_URL = "http://f15dtpai1:11517/v1"
DEFAULT_LLM_MODEL = "gpt-oss-120b"
DEFAULT_LLM_API_KEY = "EMPTY"

DEFAULT_EMBED_HOST = "f15dtpai1:11436"
DEFAULT_EMBED_MODEL = "nomic_embed_text:latest"
DEFAULT_EMBED_BATCH_SIZE = 32
DEFAULT_EMBED_MAX_WORKERS = 8


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    model_name: str
    api_key: str


@dataclass(frozen=True)
class EmbeddingConfig:
    host: str
    model: str
    batch_size: int
    max_workers: int


@dataclass(frozen=True)
class AppConfig:
    llm: LLMConfig
    embedding: EmbeddingConfig


def _parse_env_line(line: str) -> Optional[tuple[str, str]]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    return key.strip(), value.strip().strip('"').strip("'")


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(line)
        if not parsed:
            continue
        key, value = parsed
        os.environ.setdefault(key, value)


def load_config(env_path: Optional[Path] = None) -> AppConfig:
    env_file = env_path or Path.cwd() / ".env"
    load_dotenv(env_file)

    llm = LLMConfig(
        base_url=os.getenv("LLM_BASE_URL", DEFAULT_LLM_BASE_URL),
        model_name=os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL),
        api_key=os.getenv("LLM_API_KEY", DEFAULT_LLM_API_KEY),
    )
    embedding = EmbeddingConfig(
        host=os.getenv("EMBEDDING_HOST", DEFAULT_EMBED_HOST),
        model=os.getenv("EMBEDDING_MODEL", DEFAULT_EMBED_MODEL),
        batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", str(DEFAULT_EMBED_BATCH_SIZE))),
        max_workers=int(os.getenv("EMBEDDING_MAX_WORKERS", str(DEFAULT_EMBED_MAX_WORKERS))),
    )
    return AppConfig(llm=llm, embedding=embedding)
