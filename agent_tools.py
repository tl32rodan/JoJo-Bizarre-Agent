from typing import Callable, Dict


def query_internal_technical_docs(keyword: str) -> str:
    """Search internal technical documentation with a specific keyword."""
    return f"[RAG]: Technical specs for '{keyword}' (mocked)."


def query_sales_database(query_sql: str) -> str:
    """Search sales database with a SQL-like query."""
    return f"[RAG]: Sales result for '{query_sql}' is 500M (mocked)."


TOOLS_MAP: Dict[str, Callable[[str], str]] = {
    "search_docs": query_internal_technical_docs,
    "search_sales": query_sales_database,
}
