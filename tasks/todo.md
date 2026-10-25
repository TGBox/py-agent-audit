# Tasks: TokenOptimizer MCP Server & Integration

## Task 1: Dependency & Script Configuration

**Description:** Add `mcp>=1.0.0` to `pyproject.toml` dependencies and declare the console script `py-agent-audit-server = "src.server:main"`.

**Acceptance criteria:**

- [ ] `mcp` is added to `pyproject.toml` and installed via `uv sync`.
- [ ] `py-agent-audit-server` script entry exists in `[project.scripts]`.

**Verification:**

- [ ] Command succeeds: `uv run python -c "import mcp; print(mcp.__file__)"`

**Dependencies:** None  
**Files likely touched:** `pyproject.toml`, `uv.lock`  
**Estimated scope:** Small (1 file)

---

## Task 2: Implement Unified `src/server.py`

**Description:** Combine all 5 tools from `tmp/server.py` and `tmp/server-add-on.py` into a robust `src/server.py` module using `FastMCP("TokenOptimizer")`.

**Acceptance criteria:**

- [ ] Contains `run_compact_checks(project_dir: str) -> str`.
- [ ] Contains `read_python_signatures(file_path: str) -> str` with AST parsing.
- [ ] Contains `get_compact_git_diff(project_dir: str, staged_only: bool) -> str`.
- [ ] Contains `get_project_tree(project_dir: str, max_depth: int) -> str` with LOC and ignored directories.
- [ ] Contains `log_bottleneck(task_description: str, steps_taken: int, reason: str) -> str`.
- [ ] Contains `main()` function running `mcp.run()`.

**Verification:**

- [ ] Linter passes: `uv run ruff check src/server.py`

**Dependencies:** Task 1  
**Files likely touched:** `src/server.py`  
**Estimated scope:** Medium (1-2 files)

---

## Task 3: Unit Tests for MCP Tools

**Description:** Create unit tests in `tests/test_server.py` for each of the 5 tools without requiring an active external MCP client.

**Acceptance criteria:**

- [ ] Tests `read_python_signatures` on sample class and function AST nodes.
- [ ] Tests `get_project_tree` structure and LOC calculation on temporary directory.
- [ ] Tests `get_compact_git_diff` handling for clean and dirty trees.
- [ ] Tests `log_bottleneck` output in temporary JSONL log file.
- [ ] Tests `run_compact_checks` output truncation and formatting.

**Verification:**

- [ ] Tests pass: `uv run pytest tests/test_server.py`

**Dependencies:** Task 2  
**Files likely touched:** `tests/test_server.py`  
**Estimated scope:** Medium (1 file)

---

## Checkpoint: Foundation

- [ ] All 5 MCP tools tested and working (`uv run pytest tests/test_server.py`)
- [ ] `src/server.py` passes ruff check and format

---

## Task 4: Implement Claude Desktop Config Installer

**Description:** Create `src/mcp_installer.py` with `install_to_claude_desktop()` and `get_claude_desktop_config_path()`. It reads existing `%APPDATA%/Claude/claude_desktop_config.json`, backs it up, registers `py-agent-audit-optimizer`, and saves formatted JSON.

**Acceptance criteria:**

- [ ] Preserves all existing `mcpServers` entries.
- [ ] Inserts or updates `"py-agent-audit-optimizer"` with `command: "uv"` and `args: ["run", "--directory", "<project_dir>", "py-agent-audit-server"]`.
- [ ] Handles missing file or missing directory gracefully.

**Verification:**

- [ ] Linter passes: `uv run ruff check src/mcp_installer.py`

**Dependencies:** Task 2  
**Files likely touched:** `src/mcp_installer.py`  
**Estimated scope:** Small (1 file)

---

## Task 5: Unit Tests for Config Installer

**Description:** Test `src/mcp_installer.py` in `tests/test_mcp_installer.py` with mock config files.

**Acceptance criteria:**

- [ ] Tests installing to an empty or non-existent config file.
- [ ] Tests preserving existing third-party MCP servers.
- [ ] Tests backup creation.

**Verification:**

- [ ] Tests pass: `uv run pytest tests/test_mcp_installer.py`

**Dependencies:** Task 4  
**Files likely touched:** `tests/test_mcp_installer.py`  
**Estimated scope:** Small (1 file)

---

## Task 6: Audit Integration for Bottleneck Logs

**Description:** Extend `src/scanner.py` to recognize `~/.mcp_bottlenecks.jsonl` as an audited source and present reported bottlenecks as findings in the dashboard.

**Acceptance criteria:**

- [ ] `scan_bottleneck_logs(log_path: Path) -> list[Finding]` added to `src/scanner.py`.
- [ ] Included in `get_default_search_paths()`.
- [ ] Tested in `tests/test_scanner.py`.

**Verification:**

- [ ] Tests pass: `uv run pytest tests/test_scanner.py`

**Dependencies:** Task 2  
**Files likely touched:** `src/scanner.py`, `tests/test_scanner.py`  
**Estimated scope:** Small (2 files)

---

## Checkpoint: Core Integration

- [ ] Installer safely updates config without breaking other servers
- [ ] Bottleneck logs flow into the scanner

---

## Task 7: GUI 1-Click Installer Button

**Description:** Add a button "In Claude Desktop installieren" in `src/gui.py` that triggers `install_to_claude_desktop()` with confirmation dialogs. Has to describe to the user in Detail what will get installed. Maybe per Tooltip.

**Acceptance criteria:**

- [ ] Button placed in toolbar or sources header.
- [ ] Shows success confirmation dialog with the registered config path.
- [ ] Shows error dialog if writing fails.

**Verification:**

- [ ] GUI headless tests pass: `uv run pytest tests/test_gui.py`

**Dependencies:** Task 4, Task 6  
**Files likely touched:** `src/gui.py`, `tests/test_gui.py`  
**Estimated scope:** Small (2 files)

---

## Task 8: Documentation & Temporary Files Cleanup

**Description:** Update `README.md` to document the new `py-agent-audit-server` MCP tools and usage instructions, and clean up or archive `tmp/server.py` and `tmp/server-add-on.py`.

**Acceptance criteria:**

- [ ] `README.md` explains the 5 MCP tools and how to connect Claude Desktop.
- [ ] `tmp/server.py` and `tmp/server-add-on.py` are properly archived or cleaned up.

**Verification:**

- [ ] Full test suite passes: `uv run test`
- [ ] Ruff check passes: `uv run lint`

**Dependencies:** Task 7  
**Files likely touched:** `README.md`  
**Estimated scope:** Small (1 file)
