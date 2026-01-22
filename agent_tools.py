from typing import Any, Iterable, Optional, Callable, Dict

from lib.faiss_code_indexer.src.search import CodeSearcher
from lib.faiss_code_indexer.src.vector_store import FAISSStore

_SEARCHER: Optional[CodeSearcher] = None

def query_internal_technical_docs(keyword: str) -> str:
    """Search internal technical documentation with a specific keyword."""
    return f"[RAG]: Technical specs for '{keyword}' (mocked)."


def query_sales_database(query_sql: str) -> str:
    """Search sales database with a SQL-like query."""
    return f"[RAG]: Sales result for '{query_sql}' is 500M (mocked)."

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
TOOLS_MAP: Dict[str, Callable[[str], str]] = {
    "search_docs": query_internal_technical_docs,
    "search_sales": query_sales_database,
    "search_codebase": tool_code_search
}
