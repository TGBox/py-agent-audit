from pathlib import Path

from src.scanner import (
    AuditEntry,
    Finding,
    aggregate_findings,
    extract_command_key,
    generate_skill_markdown,
    scan_bottleneck_logs,
    scan_claude_logs,
    scan_copilot_sessions,
    scan_markdown_artifacts,
    scan_ollama_logs,
    scan_sources,
    scan_tool_logs,
)


def test_extract_command_key():
    assert extract_command_key("pytest tests/test_scanner.py") == "pytest tests/test_scanner.py"
    assert extract_command_key("$ git status") == "git status"
    assert extract_command_key("PS > uv run ruff check") == "uv run"
    assert extract_command_key("# this is a comment") == ""
    assert extract_command_key("") == ""
    assert extract_command_key("clear") == "clear"


def test_scan_claude_logs(tmp_path: Path):
    log_file = tmp_path / "mcp-server.log"
    log_file.write_text(
        '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "read_resource"}}\n'
        '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "read_resource"}}\n'
        '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "query_database"}}\n',
        encoding="utf-8",
    )
    findings = scan_claude_logs(tmp_path)
    assert len(findings) == 3

    entries = aggregate_findings(findings)
    assert len(entries) == 2
    assert entries[0].name == "read_resource"
    assert entries[0].count == 2
    assert entries[1].name == "query_database"
    assert entries[1].count == 1


def test_scan_markdown_artifacts(tmp_path: Path):
    md_file = tmp_path / "notes.md"
    md_file.write_text(
        "# Walkthrough\n\n```bash\npytest tests/\ngit status\n# comment\ngit status\n```\n",
        encoding="utf-8",
    )
    findings = scan_markdown_artifacts(tmp_path, provider="TestProject")
    assert len(findings) == 3

    entries = aggregate_findings(findings)
    assert entries[0].name == "git status"
    assert entries[0].count == 2
    assert entries[1].name == "pytest tests/"
    assert entries[1].count == 1


def test_scan_tool_logs(tmp_path: Path):
    json_file = tmp_path / "session.json"
    json_file.write_text(
        '{"action": "run_command", "tool": "view_file"}\n{"action": "run_command"}\n',
        encoding="utf-8",
    )
    findings = scan_tool_logs(tmp_path, provider="Antigravity")
    # run_command x2, view_file x1
    assert len(findings) == 3
    entries = aggregate_findings(findings)
    assert entries[0].name == "run_command"
    assert entries[0].count == 2
    assert entries[1].name == "view_file"
    assert entries[1].count == 1


def test_scan_copilot_sessions(tmp_path: Path):
    session_file = tmp_path / "session-123.json"
    session_file.write_text(
        "{\n"
        '  "requests": [\n'
        '    {"message": "run test", "response": ["```bash\\npytest -v\\n```"]}\n'
        "  ]\n"
        "}",
        encoding="utf-8",
    )
    findings = scan_copilot_sessions(tmp_path)
    assert len(findings) == 1
    assert findings[0].name == "pytest -v"
    assert findings[0].provider == "GitHub Copilot"


def test_scan_ollama_logs(tmp_path: Path):
    log_file = tmp_path / "server.log"
    log_file.write_text(
        '[GIN] 2026/10/09 - 20:26:32 | 200 | GET "/api/tags"\n'
        '[GIN] 2026/10/09 - 20:26:32 | 200 | POST "/api/show"\n'
        '[GIN] 2026/10/09 - 20:26:32 | 200 | POST "/api/show"\n',
        encoding="utf-8",
    )
    findings = scan_ollama_logs(tmp_path)
    assert len(findings) == 3

    entries = aggregate_findings(findings)
    assert len(entries) == 2
    assert entries[0].name == "ollama /api/show"
    assert entries[0].count == 2
    assert entries[1].name == "ollama /api/tags"
    assert entries[1].count == 1


def test_generate_skill_markdown():
    entry = AuditEntry(
        name="pytest tests/unit",
        kind="CLI Command",
        provider="Antigravity",
        count=15,
        findings=[
            Finding(
                "pytest tests/unit",
                "CLI Command",
                "Antigravity",
                Path("test.md"),
                4,
                "pytest tests/unit",
            )
        ],
    )
    skill_content = generate_skill_markdown(entry)
    assert "name: pytest-tests-unit" in skill_content
    assert "pytest tests/unit" in skill_content
    assert "15x" in skill_content


def test_scan_sources(tmp_path: Path):
    claude_dir = tmp_path / "claude"
    claude_dir.mkdir()
    (claude_dir / "mcp-test.log").write_text(
        '{"method": "tools/call", "name": "test_mcp_tool"}', encoding="utf-8"
    )

    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    (ws_dir / "plan.md").write_text("```sh\npytest -v\n```", encoding="utf-8")

    sources = [(claude_dir, "Claude Desktop"), (ws_dir, "Custom Workspace")]
    entries = scan_sources(sources)
    assert len(entries) == 2
    names = {e.name for e in entries}
    assert "test_mcp_tool" in names
    assert "pytest -v" in names


def test_scan_bottleneck_logs(tmp_path: Path):
    log_file = tmp_path / "bottlenecks.jsonl"
    log_file.write_text(
        '{"timestamp": "2026-10-25T12:00:00", "task": "Run tests repeatedly", "steps": 7, "reason": "Failing test cycle"}\n',
        encoding="utf-8",
    )
    findings = scan_bottleneck_logs(log_file)
    assert len(findings) == 1
    assert findings[0].name == "Bottleneck: Run tests repeatedly"
    assert findings[0].kind == "Agent Bottleneck"
    assert findings[0].provider == "TokenOptimizer"
    assert "7 Schritte" in findings[0].context
