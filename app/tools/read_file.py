from __future__ import annotations

from pathlib import Path


def read_file(file_path: str, *, repo_root: Path | None = None, max_bytes: int = 4000) -> str:
    """Read a file from the repo and return its contents."""
    root = repo_root or Path.cwd()
    candidate = Path(file_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError:
        return f"Error: file '{file_path}' not found."
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return "Error: file path is outside the repository."
    data = resolved.read_bytes()[:max_bytes]
    return data.decode("utf-8", errors="replace")
