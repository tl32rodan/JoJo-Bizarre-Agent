from __future__ import annotations

from pathlib import Path

from app.tools.read_file import read_file
from app.tools.search import search_codebase


def test_read_file_reads_within_repo(tmp_path: Path) -> None:
    target = tmp_path / "example.py"
    target.write_text("print('hello')\n", encoding="utf-8")

    content = read_file(str(target), repo_root=tmp_path)

    assert "print('hello')" in content


def test_read_file_rejects_outside_repo(tmp_path: Path) -> None:
    outside = tmp_path / ".." / "outside.py"

    response = read_file(str(outside), repo_root=tmp_path)

    assert response.startswith("Error:")


def test_search_codebase_finds_match(tmp_path: Path) -> None:
    target = tmp_path / "module.py"
    target.write_text("def greet():\n    return 'hello'\n", encoding="utf-8")

    result = search_codebase("greet", repo_root=tmp_path)

    assert "module.py" in result
    assert "greet" in result
