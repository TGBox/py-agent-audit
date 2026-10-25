import json
import subprocess
from pathlib import Path

from src.server import (
    detect_project_ecosystems,
    get_compact_git_diff,
    get_project_tree,
    log_bottleneck,
    read_code_signatures,
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
    assert "return a + b" not in result
    assert 'print("hello " + x)' not in result


def test_read_code_signatures_rust(tmp_path: Path):
    rs_file = tmp_path / "agent.rs"
    rs_file.write_text(
        "pub struct Agent {\n"
        "    pub id: String,\n"
        "}\n\n"
        "impl Agent {\n"
        "    pub fn run(&self) -> bool {\n"
        "        let result = 42;\n"
        "        true\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    result = read_code_signatures(str(rs_file))
    assert "pub struct Agent" in result
    assert "impl Agent" in result
    assert "pub fn run(&self) -> bool" in result
    assert "let result = 42;" not in result


def test_read_code_signatures_typescript(tmp_path: Path):
    ts_file = tmp_path / "service.ts"
    ts_file.write_text(
        "export interface UserConfig {\n"
        "  timeoutMs: number;\n"
        "}\n\n"
        "export class AuthService {\n"
        "  public authenticate(token: string): boolean {\n"
        "    const verified = true;\n"
        "    return verified;\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    result = read_code_signatures(str(ts_file))
    assert "export interface UserConfig" in result
    assert "export class AuthService" in result
    assert "authenticate(token: string): boolean" in result
    assert "const verified = true;" not in result


def test_read_code_signatures_csharp(tmp_path: Path):
    cs_file = tmp_path / "Player.cs"
    cs_file.write_text(
        "namespace Game {\n"
        "    public class PlayerController : MonoBehaviour {\n"
        "        public int Health { get; set; }\n"
        "        public void TakeDamage(int amount) {\n"
        "            Health -= amount;\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    result = read_code_signatures(str(cs_file))
    assert "public class PlayerController : MonoBehaviour" in result
    assert "public int Health { get; set; }" in result
    assert "public void TakeDamage(int amount)" in result
    assert "Health -= amount;" not in result


def test_read_python_signatures_missing_file(tmp_path: Path):
    result = read_python_signatures(str(tmp_path / "nonexistent.py"))
    assert "Error: File" in result


def test_detect_project_ecosystems(tmp_path: Path):
    assert detect_project_ecosystems(tmp_path) == []

    (tmp_path / "Cargo.toml").write_text("[package]\nname = 'test'\n", encoding="utf-8")
    assert "rust" in detect_project_ecosystems(tmp_path)

    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    assert "node" in detect_project_ecosystems(tmp_path)

    (tmp_path / "App.csproj").write_text("<Project/>", encoding="utf-8")
    assert "dotnet" in detect_project_ecosystems(tmp_path)

    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    assert "python" in detect_project_ecosystems(tmp_path)


def test_get_project_tree(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hello')\nprint('world')\n", encoding="utf-8")
    (tmp_path / "src" / "main.rs").write_text("fn main() {}\n", encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "ignored.py").write_text("x = 1\n", encoding="utf-8")

    tree = get_project_tree(str(tmp_path))
    assert "src/" in tree
    assert "app.py (2L)" in tree
    assert "main.rs (1L)" in tree
    assert ".venv" not in tree
    assert "ignored.py" not in tree


def test_get_project_tree_missing_dir(tmp_path: Path):
    result = get_project_tree(str(tmp_path / "missing_dir"))
    assert "Error: Directory" in result


def test_get_compact_git_diff(tmp_path: Path):
    assert "Error: No git repository found" in get_compact_git_diff(str(tmp_path))

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
    assert "Error: Path" in run_compact_checks(str(tmp_path / "missing"))

    # Empty directory fallback
    result = run_compact_checks(str(tmp_path))
    assert isinstance(result, str)
