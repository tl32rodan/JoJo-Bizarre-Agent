from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass(frozen=True)
class SearchResult:
    path: str
    line: int
    content: str


def _iter_source_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if path.is_file() and not path.name.startswith("."):
            yield path


def search_codebase(query: str, *, repo_root: Path | None = None, max_results: int = 5) -> str:
    """Search the codebase and return results with file paths and snippets."""
    root = repo_root or Path.cwd()
    results: List[SearchResult] = []
    for path in _iter_source_files(root):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for index, line in enumerate(lines, start=1):
            if query in line:
                results.append(SearchResult(path=str(path), line=index, content=line.strip()))
                if len(results) >= max_results:
                    break
        if len(results) >= max_results:
            break
    if not results:
        return "No results found."
    formatted = [f"{result.path}:{result.line}\n{result.content}" for result in results]
    return "\n\n".join(formatted)
