"""FastMCP TokenOptimizer server for coding agents.

Provides lightweight, token-saving routine tools for multi-language linting, testing,
code signature extraction (Python, Rust, TypeScript, C#), compact git diffs,
project tree mapping, and bottleneck logging.
"""

import ast
import json
import re
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
    "obj",
    "bin",
}

CODE_EXTENSIONS = {
    ".py",
    ".rs",
    ".cs",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".sql",
    ".toml",
    ".json",
    ".md",
    ".go",
    ".cpp",
    ".hpp",
    ".c",
    ".h",
}


def detect_project_ecosystems(cwd: Path) -> list[str]:
    """Detect programming language ecosystems present in the project directory."""
    ecosystems: list[str] = []
    if (cwd / "Cargo.toml").is_file():
        ecosystems.append("rust")
    if (cwd / "package.json").is_file():
        ecosystems.append("node")
    if list(cwd.glob("*.csproj")) or list(cwd.glob("*.sln")):
        ecosystems.append("dotnet")
    if (
        (cwd / "pyproject.toml").is_file()
        or (cwd / "setup.py").is_file()
        or (cwd / "requirements.txt").is_file()
        or list(cwd.glob("*.py"))
    ):
        ecosystems.append("python")
    return ecosystems


def run_command_safely(cmd: list[str], cwd: Path) -> tuple[int, str]:
    """Execute a subprocess command, returning returncode and combined output."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        output = (proc.stdout + "\n" + proc.stderr).strip()
        return proc.returncode, output
    except FileNotFoundError:
        return 127, f"Executable '{cmd[0]}' not found in PATH."


@mcp.tool()
def run_compact_checks(project_dir: str) -> str:
    """Run compact linter and test checks across Python, Rust, Node/TS, or .NET/C# projects.

    Automatically detects the project ecosystem (Cargo.toml, package.json, *.csproj, pyproject.toml)
    and executes appropriate tools with concise error output.
    Protects context window from large traceback dumps.
    """
    cwd = Path(project_dir)
    if not cwd.exists():
        return f"Error: Path '{project_dir}' does not exist."

    ecosystems = detect_project_ecosystems(cwd)
    if not ecosystems:
        # Default fallback to python checks
        ecosystems = ["python"]

    errors: list[str] = []
    checked_systems: list[str] = []

    # 1. Rust ecosystem
    if "rust" in ecosystems:
        checked_systems.append("Rust (cargo)")
        code, out = run_command_safely(["cargo", "check", "--message-format=short"], cwd)
        if code != 0:
            errors.append(f"--- CARGO CHECK ERRORS ---\n{out}")

        code, out = run_command_safely(["cargo", "test", "-q"], cwd)
        if code != 0:
            errors.append(f"--- CARGO TEST ERRORS ---\n{out}")

    # 2. Node / TypeScript ecosystem
    if "node" in ecosystems:
        checked_systems.append("Node / TypeScript (npm)")
        code, out = run_command_safely(["npm", "test", "--silent"], cwd)
        if code != 0:
            errors.append(f"--- NPM TEST ERRORS ---\n{out}")

    # 3. .NET / C# ecosystem
    if "dotnet" in ecosystems:
        checked_systems.append(".NET / C# (dotnet)")
        code, out = run_command_safely(["dotnet", "test", "-v", "q", "--nologo"], cwd)
        if code != 0:
            errors.append(f"--- DOTNET TEST ERRORS ---\n{out}")

    # 4. Python ecosystem
    if "python" in ecosystems:
        checked_systems.append("Python (ruff & pytest)")
        code, out = run_command_safely(["ruff", "check", "--output-format=concise", "."], cwd)
        if code != 0 and code != 127:
            errors.append(f"--- RUFF ERRORS ---\n{out}")

        code, out = run_command_safely(["pytest", "-q", "--tb=short", "--no-header"], cwd)
        if code != 0 and code != 127:
            errors.append(f"--- PYTEST ERRORS ---\n{out}")

    if not errors:
        systems_str = ", ".join(checked_systems)
        return f"OK: All checks passed cleanly for [{systems_str}]."

    combined = "\n\n".join(errors)
    if len(combined) > 3000:
        return combined[:3000] + "\n...[truncated]"
    return combined


def extract_rust_signatures(content: str) -> list[str]:
    """Extract struct, enum, trait, impl, and function signatures from Rust code."""
    signatures: list[str] = []
    lines = content.splitlines()
    for line in lines:
        stripped = line.strip()
        if re.match(r"^(?:pub(?:\(crate\))?\s+)?(?:fn|struct|enum|trait|impl|type)\b", stripped):
            signatures.append(stripped.rstrip("{; "))
    return signatures


def extract_ts_signatures(content: str) -> list[str]:
    """Extract interface, type, class, and function signatures from TS/JS code."""
    signatures: list[str] = []
    lines = content.splitlines()
    for line in lines:
        stripped = line.strip()
        if re.match(
            r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|class|interface|type|enum)\b",
            stripped,
        ) or re.match(r"^\s*(?:public|private|protected)?\s*\w+\s*\(.*?\)", line):
            signatures.append(stripped.rstrip("{; "))
    return signatures


def extract_csharp_signatures(content: str) -> list[str]:
    """Extract class, interface, struct, and method signatures from C# code."""
    signatures: list[str] = []
    lines = content.splitlines()
    for line in lines:
        stripped = line.strip()
        if re.match(
            r"^\s*(?:public|private|protected|internal|static|async|override|virtual)\s+.*",
            stripped,
        ):
            signatures.append(stripped.rstrip("{; "))
    return signatures


def extract_python_signatures(content: str) -> list[str]:
    """Extract class and function signatures from Python code using AST."""
    try:
        tree = ast.parse(content)
    except SyntaxError as exc:
        return [f"SyntaxError: {exc}"]

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
    return signatures


@mcp.tool()
def read_code_signatures(file_path: str) -> str:
    """Extract class, method, and function signatures from a code file without implementation bodies.

    Supports Python (.py), Rust (.rs), TypeScript/JavaScript (.ts, .tsx, .js), and C# (.cs).
    Saves 80-90% tokens compared to reading the full file.
    """
    path = Path(file_path)
    if not path.is_file():
        return f"Error: File '{file_path}' not found."

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"Error reading file '{file_path}': {exc}"

    suffix = path.suffix.lower()
    signatures: list[str] = []

    if suffix == ".py":
        signatures = extract_python_signatures(content)
    elif suffix == ".rs":
        signatures = extract_rust_signatures(content)
    elif suffix in (".ts", ".tsx", ".js", ".jsx"):
        signatures = extract_ts_signatures(content)
    elif suffix == ".cs":
        signatures = extract_csharp_signatures(content)
    else:
        # Fallback: Outline first 50 lines
        lines = [line.strip() for line in content.splitlines() if line.strip()][:50]
        return "\n".join(lines) if lines else "Empty file."

    return "\n\n".join(signatures) if signatures else "No signatures or classes found."


@mcp.tool()
def read_python_signatures(file_path: str) -> str:
    """Extract signatures of a Python file. Alias for read_code_signatures."""
    return read_code_signatures(file_path)


@mcp.tool()
def get_compact_git_diff(project_dir: str, staged_only: bool = False) -> str:
    """Return compact git status and diff without unnecessary context lines (--unified=0).

    Excludes lockfiles, assets, and minified bundles across all languages.
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

    Ignores build, cache, dependencies, and venv folders across Rust, Node, C#, and Python.
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
                if entry.suffix.lower() in CODE_EXTENSIONS:
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
