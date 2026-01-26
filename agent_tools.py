from __future__ import annotations

from typing import Callable, Dict

from app.tools import read_file, search_codebase


def query_internal_technical_docs(keyword: str) -> str:
    """Search internal technical documentation with a specific keyword."""
    return f"[RAG]: Technical specs for '{keyword}' (mocked)."


def query_sales_database(query_sql: str) -> str:
    """Search sales database with a SQL-like query."""
    return f"[RAG]: Sales result for '{query_sql}' is 500M (mocked)."


def tool_code_search(query: str) -> str:
    """Search the codebase and return results with file paths and snippets."""
    return search_codebase(query)


def tool_read_file(path: str) -> str:
    """Read a file from the codebase to expand context."""
    return read_file(path)


TOOLS_MAP: Dict[str, Callable[[str], str]] = {
    "search_docs": query_internal_technical_docs,
    "search_sales": query_sales_database,
    "search_codebase": tool_code_search,
    "read_file": tool_read_file,
}
