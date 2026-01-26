import agent_tools


def test_query_internal_docs_returns_message() -> None:
    result = agent_tools.query_internal_technical_docs("latency")

    assert "latency" in result


def test_query_sales_database_returns_message() -> None:
    result = agent_tools.query_sales_database("select *")

    assert "select" in result


def test_tool_code_search_delegates(monkeypatch) -> None:
    def fake_search(query: str) -> str:
        return f"fake:{query}"

    monkeypatch.setattr(agent_tools, "search_codebase", fake_search)

    assert agent_tools.tool_code_search("hello") == "fake:hello"


def test_tool_read_file_delegates(monkeypatch) -> None:
    def fake_read(path: str) -> str:
        return f"read:{path}"

    monkeypatch.setattr(agent_tools, "read_file", fake_read)

    assert agent_tools.tool_read_file("app.py") == "read:app.py"
