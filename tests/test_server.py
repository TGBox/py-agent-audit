import json
import subprocess
from pathlib import Path

from src.server import (
    get_compact_git_diff,
    get_project_tree,
    log_bottleneck,
    read_python_signatures,
    run_compact_checks,
)


def test_read_python_signatures(tmp_path: Path):
    py_file = tmp_path / "sample.py"
    py_file.write_text(
        "class Calculator:\n"
        "    version: str\n"
        "    def add(self, a: int, b: int) -> int:\n"
        "        return a + b\n\n"
        "def standalone_func(x: str) -> None:\n"
        '    print("hello " + x)\n',
        encoding="utf-8",
    )
    result = read_python_signatures(str(py_file))
    assert "class Calculator:" in result
    assert "def add(self, a: int, b: int) -> int:" in result
    assert "def standalone_func(x: str) -> None:" in result
    # Function bodies should be replaced by ellipsis (...)
    assert "return a + b" not in result
    assert 'print("hello " + x)' not in result


def test_read_python_signatures_missing_file(tmp_path: Path):
    result = read_python_signatures(str(tmp_path / "nonexistent.py"))
    assert "Error: File" in result


def test_get_project_tree(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hello')\nprint('world')\n", encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "ignored.py").write_text("x = 1\n", encoding="utf-8")

    tree = get_project_tree(str(tmp_path))
    assert "src/" in tree
    assert "app.py (2L)" in tree
    assert ".venv" not in tree
    assert "ignored.py" not in tree


def test_get_project_tree_missing_dir(tmp_path: Path):
    result = get_project_tree(str(tmp_path / "missing_dir"))
    assert "Error: Directory" in result


def test_get_compact_git_diff(tmp_path: Path):
    # Non-git directory
    assert "Error: No git repository found" in get_compact_git_diff(str(tmp_path))

    # Initialize a git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    clean_result = get_compact_git_diff(str(tmp_path))
    assert "Working tree is clean" in clean_result


def test_log_bottleneck(tmp_path: Path, monkeypatch):
    log_path = tmp_path / "bottlenecks.jsonl"
    monkeypatch.setattr("src.server.BOTTLENECK_LOG", log_path)

    resp = log_bottleneck("Fix regex issue", 5, "Agent cycled 5 times without resolving")
    assert "Bottleneck logged successfully" in resp
    assert log_path.exists()

    content = log_path.read_text(encoding="utf-8").strip()
    data = json.loads(content)
    assert data["task"] == "Fix regex issue"
    assert data["steps"] == 5
    assert data["reason"] == "Agent cycled 5 times without resolving"


def test_run_compact_checks(tmp_path: Path):
    # Missing directory
    assert "Error: Path" in run_compact_checks(str(tmp_path / "missing"))

    # Empty directory
    result = run_compact_checks(str(tmp_path))
    assert isinstance(result, str)
