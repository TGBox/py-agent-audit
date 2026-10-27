"""FastMCP TokenOptimizer server for coding agents.

Provides lightweight, token-saving routine tools for multi-language linting, testing,
code signature extraction (Python, Rust, TypeScript, C#), compact git diffs,
project tree mapping, and bottleneck logging.
"""

import ast
import json
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except (ImportError, ModuleNotFoundError):
    from mcp.server.fastmcp import FastMCP  # type: ignore[no-redef]

# Initialise FastMCP Server
mcp = FastMCP("TokenOptimizer")

BOTTLENECK_LOG = Path.home() / ".mcp_bottlenecks.jsonl"

CHECK_TIMEOUT_SECONDS = 300
EXIT_NOT_FOUND = 127
EXIT_TIMEOUT = 124
PYTEST_NO_TESTS_COLLECTED = 5
MAX_SECTION_CHARS = 1500

# Lockfiles and generated assets excluded from compact diffs. Exact names instead of
# "*lock*", which also matched source files like "blocker.py" or "clock.rs".
DIFF_EXCLUDES = [
    "Cargo.lock",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
    "uv.lock",
    "poetry.lock",
    "Pipfile.lock",
    "composer.lock",
    "Gemfile.lock",
    "packages.lock.json",
    "*.svg",
    "*.min.js",
    "*.min.css",
    "*.map",
]

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


def _clean_subprocess_env() -> dict[str, str]:
    """Return an environment for child processes without this server's own virtualenv.

    The server itself runs via ``uv run`` inside the py-agent-audit venv. Without cleanup,
    ``pytest``/``ruff`` of *this* venv would be used for the target project.
    """
    env = dict(os.environ)
    own_venv = env.pop("VIRTUAL_ENV", None)
    if own_venv:
        own_bins = {os.path.normcase(str(Path(own_venv) / sub)) for sub in ("bin", "Scripts")}
        env["PATH"] = os.pathsep.join(
            p for p in env.get("PATH", "").split(os.pathsep) if os.path.normcase(p) not in own_bins
        )
    # Non-interactive mode: prevents watch modes (vitest/jest) and colour codes.
    env["CI"] = "1"
    env.setdefault("NO_COLOR", "1")
    return env


def run_command_safely(
    cmd: list[str],
    cwd: Path,
    timeout: int = CHECK_TIMEOUT_SECONDS,
    stdout_only: bool = False,
) -> tuple[int, str]:
    """Execute a subprocess command, returning returncode and combined output.

    With ``stdout_only`` the raw, unstripped stdout is returned on success (stderr is
    only returned on failure). stdin is detached: the MCP server talks JSON-RPC over its
    own stdin, a child process must never read from it.
    """
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_clean_subprocess_env(),
            timeout=timeout,
            check=False,
        )
        if stdout_only and proc.returncode == 0:
            return proc.returncode, proc.stdout
        output = (proc.stdout + "\n" + proc.stderr).strip()
        return proc.returncode, output
    except FileNotFoundError:
        return EXIT_NOT_FOUND, f"Executable '{cmd[0]}' not found in PATH."
    except subprocess.TimeoutExpired:
        return EXIT_TIMEOUT, f"'{' '.join(cmd)}' aborted after {timeout}s (timeout)."


def _is_tool_missing(code: int, output: str, tool: str) -> bool:
    """True if a command could not start because the tool itself is not installed."""
    if code == EXIT_NOT_FOUND:
        return True
    if code == 0:
        return False
    # `uv run <tool>` prints "Failed to spawn: `<tool>`"; `python -m <tool>` prints
    # "No module named <tool>" (exact module, so ImportErrors inside tests don't match).
    return (
        f"Failed to spawn: `{tool}`" in output
        or re.search(rf"No module named '?{re.escape(tool)}'?\s*$", output, re.MULTILINE)
        is not None
    )


def _python_runner(cwd: Path) -> list[str]:
    """Return the command prefix used to run Python tools inside the target project."""
    if (cwd / "uv.lock").is_file() and shutil.which("uv"):
        return ["uv", "run"]
    for venv_name in (".venv", "venv"):
        for python in (
            cwd / venv_name / "Scripts" / "python.exe",
            cwd / venv_name / "bin" / "python",
        ):
            if python.is_file():
                return [str(python), "-m"]
    return ["python", "-m"]


def _tail(text: str, limit: int) -> str:
    """Keep the end of a long output; summaries of test runners are at the bottom."""
    if len(text) <= limit:
        return text
    return "...[truncated]\n" + text[-limit:]


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
    skipped: list[str] = []
    passed: list[str] = []

    def check(label: str, cmd: list[str], tool: str, ok_codes: tuple[int, ...] = (0,)) -> None:
        code, out = run_command_safely(cmd, cwd)
        if code in ok_codes:
            passed.append(label)
        elif _is_tool_missing(code, out, tool):
            # Never report a check as passed that did not run at all.
            skipped.append(f"{label}: '{tool}' not available ({' '.join(cmd)})")
        elif code == EXIT_TIMEOUT:
            errors.append(f"--- {label.upper()} TIMEOUT ---\n{out}")
        else:
            errors.append(f"--- {label.upper()} ERRORS ---\n{_tail(out, MAX_SECTION_CHARS)}")

    # 1. Rust ecosystem
    if "rust" in ecosystems:
        check("cargo check", ["cargo", "check", "--message-format=short"], "cargo")
        check("cargo test", ["cargo", "test", "-q"], "cargo")

    # 2. Node / TypeScript ecosystem
    if "node" in ecosystems:
        check("npm test", ["npm", "test", "--silent"], "npm")

    # 3. .NET / C# ecosystem
    if "dotnet" in ecosystems:
        check("dotnet test", ["dotnet", "test", "-v", "q", "--nologo"], "dotnet")

    # 4. Python ecosystem (run inside the target project's environment)
    if "python" in ecosystems:
        runner = _python_runner(cwd)
        check("ruff", [*runner, "ruff", "check", "--output-format=concise", "."], "ruff")
        check(
            "pytest",
            [*runner, "pytest", "-q", "--tb=short", "--no-header"],
            "pytest",
            ok_codes=(0, PYTEST_NO_TESTS_COLLECTED),
        )

    sections: list[str] = []
    if errors:
        sections.append("FAILED")
        sections.extend(errors)
    if skipped:
        sections.append("--- NOT RUN ---\n" + "\n".join(f"- {s}" for s in skipped))
    if passed:
        sections.append("Passed: " + ", ".join(passed))

    if not errors and not skipped:
        return f"OK: All checks passed cleanly [{', '.join(passed)}]."
    if not errors:
        return "INCOMPLETE: no failures, but some checks could not run.\n\n" + "\n\n".join(sections)
    return "\n\n".join(sections)


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
    if not cwd.is_dir():
        return f"Error: No git repository found in '{project_dir}'."

    # rev-parse also works from subdirectories and in worktrees (where .git is a file).
    code, out = run_command_safely(["git", "rev-parse", "--is-inside-work-tree"], cwd)
    if code == EXIT_NOT_FOUND:
        return "Error: Git executable not found in PATH."
    if code != 0 or out.strip() != "true":
        return f"Error: No git repository found in '{project_dir}'."

    code, status_out = run_command_safely(["git", "status", "--short"], cwd, stdout_only=True)
    if code != 0:
        return f"Error running git status: {status_out}"
    # Only strip trailing whitespace: the leading space of " M file" carries meaning
    # (unstaged vs. staged "M  file").
    status = status_out.rstrip()

    if not status and not staged_only:
        return "Working tree is clean (no changes)."

    diff_cmd = ["git", "diff", "--unified=0", "--no-color"]
    if staged_only:
        diff_cmd.append("--staged")
    diff_cmd.extend(["--", "."])
    diff_cmd.extend(f":(glob,exclude)**/{pattern}" for pattern in DIFF_EXCLUDES)

    code, diff = run_command_safely(diff_cmd, cwd, stdout_only=True)
    if code != 0:
        return f"Error running git diff: {diff}"

    output = f"=== STATUS ===\n{status}\n\n=== COMPACT DIFF (U=0) ===\n{diff.strip()}"
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
        "timestamp": datetime.now(UTC).astimezone().isoformat(timespec="seconds"),
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
