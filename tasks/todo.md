# Tasks: TokenOptimizer MCP Server & Integration

## Task 1: Dependency & Script Configuration

**Description:** Add `mcp>=1.0.0` to `pyproject.toml` dependencies and declare the console script `py-agent-audit-server = "src.server:main"`.

**Acceptance criteria:**

- [x] `mcp` is added to `pyproject.toml` and installed via `uv sync`.
- [x] `py-agent-audit-server` script entry exists in `[project.scripts]`.

**Verification:**

- [x] Command succeeds: `uv run python -c "import mcp; print(mcp.__file__)"`

**Dependencies:** None  
**Files likely touched:** `pyproject.toml`, `uv.lock`  
**Estimated scope:** Small (1 file)

---

## Task 2: Implement Unified `src/server.py`

**Description:** Combine all 5 tools from `tmp/server.py` and `tmp/server-add-on.py` into a robust `src/server.py` module using `FastMCP("TokenOptimizer")`.

**Acceptance criteria:**

- [x] Contains `run_compact_checks(project_dir: str) -> str`.
- [x] Contains `read_python_signatures(file_path: str) -> str` with AST parsing.
- [x] Contains `get_compact_git_diff(project_dir: str, staged_only: bool) -> str`.
- [x] Contains `get_project_tree(project_dir: str, max_depth: int) -> str` with LOC and ignored directories.
- [x] Contains `log_bottleneck(task_description: str, steps_taken: int, reason: str) -> str`.
- [x] Contains `main()` function running `mcp.run()`.

**Verification:**

- [x] Linter passes: `uv run ruff check src/server.py`

**Dependencies:** Task 1  
**Files likely touched:** `src/server.py`  
**Estimated scope:** Medium (1-2 files)

---

## Task 3: Unit Tests for MCP Tools

**Description:** Create unit tests in `tests/test_server.py` for each of the 5 tools without requiring an active external MCP client.

**Acceptance criteria:**

- [x] Tests `read_python_signatures` on sample class and function AST nodes.
- [x] Tests `get_project_tree` structure and LOC calculation on temporary directory.
- [x] Tests `get_compact_git_diff` handling for clean and dirty trees.
- [x] Tests `log_bottleneck` output in temporary JSONL log file.
- [x] Tests `run_compact_checks` output truncation and formatting.

**Verification:**

- [x] Tests pass: `uv run pytest tests/test_server.py`

**Dependencies:** Task 2  
**Files likely touched:** `tests/test_server.py`  
**Estimated scope:** Medium (1 file)

---

## Checkpoint: Foundation

- [x] All 5 MCP tools tested and working (`uv run pytest tests/test_server.py`)
- [x] `src/server.py` passes ruff check and format

---

## Task 4: Implement Claude Desktop Config Installer

**Description:** Create `src/mcp_installer.py` with `install_to_claude_desktop()` and `get_claude_desktop_config_path()`. It reads existing `%APPDATA%/Claude/claude_desktop_config.json`, backs it up, registers `py-agent-audit-optimizer`, and saves formatted JSON.

**Acceptance criteria:**

- [x] Preserves all existing `mcpServers` entries.
- [x] Inserts or updates `"py-agent-audit-optimizer"` with `command: "uv"` and `args: ["run", "--directory", "<project_dir>", "py-agent-audit-server"]`.
- [x] Handles missing file or missing directory gracefully.

**Verification:**

- [x] Linter passes: `uv run ruff check src/mcp_installer.py`

**Dependencies:** Task 2  
**Files likely touched:** `src/mcp_installer.py`  
**Estimated scope:** Small (1 file)

---

## Task 5: Unit Tests for Config Installer

**Description:** Test `src/mcp_installer.py` in `tests/test_mcp_installer.py` with mock config files.

**Acceptance criteria:**

- [x] Tests installing to an empty or non-existent config file.
- [x] Tests preserving existing third-party MCP servers.
- [x] Tests backup creation.

**Verification:**

- [x] Tests pass: `uv run pytest tests/test_mcp_installer.py`

**Dependencies:** Task 4  
**Files likely touched:** `tests/test_mcp_installer.py`  
**Estimated scope:** Small (1 file)

---

## Task 6: Audit Integration for Bottleneck Logs

**Description:** Extend `src/scanner.py` to recognize `~/.mcp_bottlenecks.jsonl` as an audited source and present reported bottlenecks as findings in the dashboard.

**Acceptance criteria:**

- [x] `scan_bottleneck_logs(log_path: Path) -> list[Finding]` added to `src/scanner.py`.
- [x] Included in `get_default_search_paths()`.
- [x] Tested in `tests/test_scanner.py`.

**Verification:**

- [x] Tests pass: `uv run pytest tests/test_scanner.py`

**Dependencies:** Task 2  
**Files likely touched:** `src/scanner.py`, `tests/test_scanner.py`  
**Estimated scope:** Small (2 files)

---

## Checkpoint: Core Integration

- [x] Installer safely updates config without breaking other servers
- [x] Bottleneck logs flow into the scanner

---

## Task 7: GUI 1-Click Installer Button

**Description:** Add a button "In Claude Desktop installieren" in `src/gui.py` that triggers `install_to_claude_desktop()` with confirmation dialogs. Has to describe to the user in Detail what will get installed. Maybe per Tooltip.

**Acceptance criteria:**

- [x] Button placed in toolbar or sources header.
- [x] Shows success confirmation dialog with the registered config path.
- [x] Shows error dialog if writing fails.

**Verification:**

- [x] GUI headless tests pass: `uv run pytest tests/test_gui.py`

**Dependencies:** Task 4, Task 6  
**Files likely touched:** `src/gui.py`, `tests/test_gui.py`  
**Estimated scope:** Small (2 files)

---

## Task 8: Documentation & Temporary Files Cleanup

**Description:** Update `README.md` to document the new `py-agent-audit-server` MCP tools and usage instructions, and clean up or archive `tmp/server.py` and `tmp/server-add-on.py`.

**Acceptance criteria:**

- [x] `README.md` explains the 5 MCP tools and how to connect Claude Desktop.
- [x] `tmp/server.py` and `tmp/server-add-on.py` functionality is fully integrated into `src/server.py`.

**Verification:**

- [x] Full test suite passes: `uv run test`
- [x] Ruff check passes: `uv run lint`

**Dependencies:** Task 7  
**Files likely touched:** `README.md`  
**Estimated scope:** Small (1 file)

---

## Task 9: Polyglot Support (Rust, Node/TS, C#, Python)

**Description:** Extend the FastMCP TokenOptimizer server (`src/server.py`) to support multi-language projects: auto-detecting ecosystem in `run_compact_checks` (Rust, Node/TS, .NET, Python), multi-language signature extraction in `read_code_signatures`, and cross-ecosystem build directory ignore rules.

**Acceptance criteria:**

- [x] `detect_project_ecosystems()` recognizes Cargo, npm/yarn, dotnet, and Python markers.
- [x] `run_compact_checks()` executes ecosystem-appropriate checks (`cargo check`, `npm test`, `dotnet build`, `ruff`/`pytest`).
- [x] `read_code_signatures()` extracts structural definitions for `.py`, `.rs`, `.ts`/`.js`, and `.cs` files while stripping method bodies.
- [x] Aliased backwards-compatible `read_python_signatures()` maintained.
- [x] Git diff & project tree ignores build artifacts (`target`, `node_modules`, `bin`, `obj`, `.venv`).
- [x] Tested in `tests/test_server.py`.

**Verification:**

- [x] All polyglot tests pass: `uv run pytest tests/test_server.py`
- [x] Ruff lint & formatting clean: `uv run ruff check .`

