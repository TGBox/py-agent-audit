# Implementation Plan: TokenOptimizer MCP Server & Integration

## Overview

Integration of a dedicated Model Context Protocol (MCP) server (`TokenOptimizer`) based on FastMCP into `py-agent-audit`. The server combines 5 token-saving routine tools (compact checks, AST signatures, compact git diff, project tree, bottleneck logging), includes a 1-click installer for Claude Desktop, and feeds bottleneck logs back into the audit dashboard.

## Architecture Decisions

- **Dependency**: Add `mcp>=1.0.0` to `pyproject.toml` dependencies.
- **Server Module (`src/server.py`)**: Unified FastMCP application instance exposing all 5 tools, callable via `uv run py-agent-audit-server`.
- **Config Installer (`src/mcp_installer.py`)**: Independent, testable helper to register the server in Claude Desktop's `claude_desktop_config.json` without destroying existing third-party servers.
- **Scanner Extension (`src/scanner.py`)**: Auto-detection of `~/.mcp_bottlenecks.jsonl` as an additional audit source.
- **UI Integration (`src/gui.py`)**: Toolbar action button "MCP in Claude Desktop installieren" with user confirmation and status feedback.

---

## Task List

### Phase 1: Core MCP Server & Tool Fusion

- [ ] Task 1: Add `mcp` dependency and project script `py-agent-audit-server`
- [ ] Task 2: Implement unified `src/server.py` with all 5 tools
- [ ] Task 3: Implement comprehensive unit tests for `src/server.py` in `tests/test_server.py`

### Checkpoint: Phase 1

- [ ] All 5 MCP tools tested and working (`uv run pytest tests/test_server.py`)
- [ ] Server starts cleanly via command line

### Phase 2: Claude Desktop Installer & Bottleneck Logging

- [ ] Task 4: Implement `src/mcp_installer.py` for safe Claude Desktop config patching
- [ ] Task 5: Add tests for config installer in `tests/test_mcp_installer.py`
- [ ] Task 6: Extend `src/scanner.py` to parse `~/.mcp_bottlenecks.jsonl` and test in `tests/test_scanner.py`

### Checkpoint: Phase 2

- [ ] Installer safely creates or modifies `claude_desktop_config.json`
- [ ] Bottleneck log entries are recognized by scanner and aggregated in audit results

### Phase 3: GUI Integration & End-to-End Polish

- [ ] Task 7: Add 1-Click "MCP in Claude Desktop installieren" button and status handling in `src/gui.py`
- [ ] Task 8: Update headless GUI tests in `tests/test_gui.py`
- [ ] Task 9: Update `README.md` and archive temporary scripts in `tmp/`

### Checkpoint: Phase 3

- [ ] Complete test suite passes (`uv run pytest`)
- [ ] Ruff lint & format clean (`uv run lint`, `uv run format`)
- [ ] End-to-end verification

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
| ------ | -------- | ------------ |
| Claude Desktop config JSON is corrupted or in invalid format | High | Atomic backup (`.bak`) before writing; parse with error recovery |
| Subprocess calls (ruff/pytest/git) fail if tools are not installed in target project | Medium | Return graceful error string instead of crashing the MCP server |
| File encoding issues in AST parser on exotic files | Low | UTF-8 with fallback/errors handling |
