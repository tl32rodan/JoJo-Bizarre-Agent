import sys
from pathlib import Path
from typing import Any, Iterable, Optional

FAISS_ROOT = (Path(__file__).resolve().parent / ".." / "faiss-for-code-indexing").resolve()
sys.path.append(str(FAISS_ROOT))

from src.search import CodeSearcher  # noqa: E402
from src.vector_store import FAISSStore  # noqa: E402

_SEARCHER: Optional[CodeSearcher] = None


def initialize_search_engine(index_path: str) -> CodeSearcher:
    """Initialize and cache the FAISS-backed code search engine."""
    global _SEARCHER
    store = FAISSStore(index_path=index_path)
    _SEARCHER = CodeSearcher(store)
    return _SEARCHER


def _format_result(result: Any) -> str:
    if isinstance(result, dict):
        path = result.get("path") or result.get("file_path") or "<unknown>"
        snippet = result.get("snippet") or result.get("content") or ""
    else:
        path = getattr(result, "path", None) or getattr(result, "file_path", None) or "<unknown>"
        snippet = getattr(result, "snippet", None) or getattr(result, "content", None) or ""
    return f"{path}\n{snippet}".rstrip()


def _iter_results(results: Any) -> Iterable[Any]:
    if results is None:
        return []
    if isinstance(results, list):
        return results
    return list(results)


def tool_code_search(query: str) -> str:
    """Search the codebase and return results with file paths and snippets."""
    if _SEARCHER is None:
        raise RuntimeError("Search engine not initialized. Call initialize_search_engine first.")
    results = _iter_results(_SEARCHER.search(query))
    if not results:
        return "No results found."
    formatted = [_format_result(result) for result in results]
    return "\n\n".join(formatted)


TOOLS_MAP = {"search_codebase": tool_code_search}
