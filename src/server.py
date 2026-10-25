"""FastMCP TokenOptimizer server for coding agents.

Provides lightweight, token-saving routine tools for linting, testing,
AST signature extraction, compact git diffs, project tree mapping, and bottleneck logging.
"""

import ast
import json
import subprocess
from datetime import datetime
from pathlib import Path

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except (ImportError, ModuleNotFoundError):
    from mcp.server.fastmcp import FastMCP  # type: ignore[no-redef]

# Initialise FastMCP Server
mcp = FastMCP("TokenOptimizer")

BOTTLENECK_LOG = Path.home() / ".mcp_bottlenecks.jsonl"

IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "target",
    "build",
    "dist",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
    ".agents",
}

CODE_EXTENSIONS = {".py", ".rs", ".cs", ".ts", ".js", ".sql", ".toml", ".json", ".md"}


@mcp.tool()
def run_compact_checks(project_dir: str) -> str:
    """Run linter (ruff) and tests (pytest) with compact output.

    Returns 'OK' on success or concise error lines only.
    Protects context window from large traceback dumps.
    """
    cwd = Path(project_dir)
    if not cwd.exists():
        return f"Error: Path '{project_dir}' does not exist."

    errors: list[str] = []

    # 1. Ruff Linter
    try:
        ruff = subprocess.run(
            ["ruff", "check", "--output-format=concise", "."],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        if ruff.returncode != 0:
            errors.append(f"--- RUFF ERRORS ---\n{ruff.stdout.strip()}")
    except FileNotFoundError:
        errors.append("--- RUFF NOTICE ---\nRuff is not installed in environment.")

    # 2. Pytest
    try:
        pytest = subprocess.run(
            ["pytest", "-q", "--tb=short", "--no-header"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        if pytest.returncode != 0:
            errors.append(f"--- PYTEST ERRORS ---\n{pytest.stdout.strip()}")
    except FileNotFoundError:
        errors.append("--- PYTEST NOTICE ---\nPytest is not installed in environment.")

    if not errors:
        return "OK: All linter and test checks passed cleanly."

    combined = "\n\n".join(errors)
    if len(combined) > 3000:
        return combined[:3000] + "\n...[truncated]"
    return combined


@mcp.tool()
def read_python_signatures(file_path: str) -> str:
    """Extract class, method, function signatures and type-hints of a Python file without implementation bodies.

    Saves 80-90% tokens compared to reading the entire file.
    """
    path = Path(file_path)
    if not path.is_file():
        return f"Error: File '{file_path}' not found."

    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError as exc:
        return f"SyntaxError in {file_path}: {exc}"

    signatures: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node.body = [ast.Expr(ast.Constant(...))]
            signatures.append(ast.unparse(node))
        elif isinstance(node, ast.ClassDef):
            clean_body: list[ast.stmt] = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    item.body = [ast.Expr(ast.Constant(...))]
                    clean_body.append(item)
                elif isinstance(item, ast.AnnAssign):
                    clean_body.append(item)
            node.body = clean_body or [ast.Expr(ast.Constant(...))]
            signatures.append(ast.unparse(node))

    return "\n\n".join(signatures) if signatures else "No classes or functions found."


@mcp.tool()
def get_compact_git_diff(project_dir: str, staged_only: bool = False) -> str:
    """Return compact git status and diff without unnecessary context lines (--unified=0).

    Excludes lockfiles, assets, and minified bundles to minimize token usage.
    """
    cwd = Path(project_dir)
    if not (cwd / ".git").exists():
        return f"Error: No git repository found in '{project_dir}'."

    try:
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
    except FileNotFoundError:
        return "Error: Git executable not found in PATH."

    if not status and not staged_only:
        return "Working tree is clean (no changes)."

    diff_cmd = ["git", "diff", "--unified=0", "--no-color"]
    if staged_only:
        diff_cmd.append("--staged")
    diff_cmd.extend(
        [
            "--",
            ".",
            ":(exclude)*lock*",
            ":(exclude)*.svg",
            ":(exclude)*.min.*",
        ]
    )

    diff = subprocess.run(
        diff_cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()

    output = f"=== STATUS ===\n{status}\n\n=== COMPACT DIFF (U=0) ===\n{diff}"
    if len(output) > 4000:
        return output[:4000] + "\n...[Diff truncated]"
    return output


@mcp.tool()
def get_project_tree(project_dir: str, max_depth: int = 3) -> str:
    """Return directory structure with line counts (LOC) for code files.

    Ignores build, cache, dependencies, and venv folders to reduce token waste.
    """
    root = Path(project_dir)
    if not root.is_dir():
        return f"Error: Directory '{project_dir}' does not exist."

    lines: list[str] = [f"{root.name}/"]

    def _walk(current: Path, depth: int, prefix: str) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(
                [p for p in current.iterdir() if p.name not in IGNORE_DIRS],
                key=lambda p: (p.is_file(), p.name.lower()),
            )
        except PermissionError:
            return

        for idx, entry in enumerate(entries):
            is_last = idx == len(entries) - 1
            connector = "└── " if is_last else "├── "

            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                extension = "    " if is_last else "│   "
                _walk(entry, depth + 1, prefix + extension)
            else:
                loc_info = ""
                if entry.suffix in CODE_EXTENSIONS:
                    try:
                        loc = sum(1 for _ in entry.open("rb"))
                        loc_info = f" ({loc}L)"
                    except OSError:
                        pass
                lines.append(f"{prefix}{connector}{entry.name}{loc_info}")

    _walk(root, 1, "")
    result = "\n".join(lines)
    if len(result) > 4000:
        return result[:4000] + "\n...[Tree truncated]"
    return result


@mcp.tool()
def log_bottleneck(task_description: str, steps_taken: int, reason: str) -> str:
    """Log an agent task that required excessive steps or repeated attempts.

    Records entries into ~/.mcp_bottlenecks.jsonl for subsequent py-agent-audit analysis.
    """
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "task": task_description,
        "steps": steps_taken,
        "reason": reason,
    }
    try:
        with BOTTLENECK_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return "Bottleneck logged successfully."
    except OSError as exc:
        return f"Error writing bottleneck log: {exc}"


def main() -> None:
    """Run the FastMCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
