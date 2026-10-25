"""Scanner module for auditing AI coding agent logs, artifacts, and multi-source workflows."""

import json
import os
import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Regex patterns for matching tool calls and shell commands
MCP_TOOL_PATTERN = re.compile(r'"method"\s*:\s*"tools/call".*?"name"\s*:\s*"([^"]+)"', re.DOTALL)
CODE_BLOCK_PATTERN = re.compile(
    r"```(?:bash|powershell|sh|cmd|shell|ps1)\r?\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)
ANTIGRAVITY_TOOL_PATTERN = re.compile(
    r"\b(run_command|view_file|replace_file_content|multi_replace_file_content|"
    r"grep_search|find_by_name|list_dir|write_to_file|ask_question|browser_subagent)\b"
)
OLLAMA_API_PATTERN = re.compile(r'(?:POST|GET)\s+"(/api/[^"]+)"')


@dataclass(slots=True)
class Finding:
    """Represents a single occurrence of a command or tool usage."""

    name: str
    kind: str  # e.g., 'CLI Command', 'MCP Tool', 'Internal Tool', 'LLM Endpoint'
    provider: str  # e.g., 'Claude Desktop', 'Antigravity', 'GitHub Copilot', 'Ollama', 'Workspace'
    file_path: Path
    line_number: int | None = None
    context: str = ""


@dataclass(slots=True)
class AuditEntry:
    """Aggregated entry for a recurring command or tool."""

    name: str
    kind: str
    provider: str
    count: int = 0
    findings: list[Finding] = field(default_factory=list)


def extract_command_key(line: str) -> str:
    """Extract a normalized command key (first 1-2 command tokens)."""
    clean_line = re.sub(r"^(?:\$|>\s*|PS\s*>\s*)", "", line).strip()
    if not clean_line or clean_line.startswith(("#", "::")):
        return ""
    parts = clean_line.split()
    if not parts:
        return ""
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1]}"
    return parts[0]


def extract_strings_from_json(data: Any) -> list[str]:
    """Recursively extract all string values from a JSON structure."""
    strings: list[str] = []
    if isinstance(data, str):
        strings.append(data)
    elif isinstance(data, list):
        for item in data:
            strings.extend(extract_strings_from_json(item))
    elif isinstance(data, dict):
        for val in data.values():
            strings.extend(extract_strings_from_json(val))
    return strings


def get_default_search_paths() -> dict[str, list[Path]]:
    """Return default search directories per provider based on OS environment."""
    appdata = Path(os.environ.get("APPDATA", ""))
    localappdata = Path(os.environ.get("LOCALAPPDATA", ""))
    userprofile = Path(os.environ.get("USERPROFILE", Path.home()))

    paths: dict[str, list[Path]] = {
        "Claude Desktop": [],
        "Antigravity": [],
        "GitHub Copilot": [],
        "Ollama": [],
        "Claude Code": [],
    }

    # Claude Desktop
    claude_log_dir = appdata / "Claude" / "logs"
    if claude_log_dir.exists():
        paths["Claude Desktop"].append(claude_log_dir)

    # Antigravity / Gemini
    ag_candidates = [
        userprofile / ".gemini" / "antigravity",
        userprofile / ".gemini" / "antigravity-ide",
        appdata / "Antigravity" / "logs",
    ]
    for candidate in ag_candidates:
        if candidate.exists():
            paths["Antigravity"].append(candidate)

    # GitHub Copilot (VS Code Chat Sessions)
    copilot_dirs = [
        appdata / "Code" / "User" / "globalStorage" / "emptyWindowChatSessions",
        appdata / "Code" / "User" / "globalStorage" / "github.copilot-chat",
    ]
    for c_dir in copilot_dirs:
        if c_dir.exists():
            paths["GitHub Copilot"].append(c_dir)

    # Ollama
    ollama_log = localappdata / "Ollama" / "server.log"
    if ollama_log.exists():
        paths["Ollama"].append(ollama_log.parent)

    # Claude Code CLI
    claude_code_dir = userprofile / ".claude"
    if claude_code_dir.exists():
        paths["Claude Code"].append(claude_code_dir)

    return paths


def scan_claude_logs(log_dir: Path) -> list[Finding]:
    """Scan Claude Desktop MCP log files for tool calls."""
    findings: list[Finding] = []
    if not log_dir.exists():
        return findings

    for log_file in log_dir.glob("mcp*.log"):
        try:
            content = log_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for line_idx, line in enumerate(content.splitlines(), start=1):
            for match in MCP_TOOL_PATTERN.finditer(line):
                tool_name = match.group(1)
                findings.append(
                    Finding(
                        name=tool_name,
                        kind="MCP Tool",
                        provider="Claude Desktop",
                        file_path=log_file,
                        line_number=line_idx,
                        context=line.strip()[:200],
                    )
                )
    return findings


def scan_markdown_artifacts(base_dir: Path, provider: str = "Workspace") -> list[Finding]:
    """Scan markdown files for shell commands inside code blocks."""
    findings: list[Finding] = []
    if not base_dir.exists():
        return findings

    for md_file in base_dir.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for block in CODE_BLOCK_PATTERN.findall(content):
            for line in block.splitlines():
                cmd_key = extract_command_key(line)
                if cmd_key:
                    findings.append(
                        Finding(
                            name=cmd_key,
                            kind="CLI Command",
                            provider=provider,
                            file_path=md_file,
                            line_number=None,
                            context=line.strip()[:200],
                        )
                    )
    return findings


def scan_tool_logs(base_dir: Path, provider: str = "Antigravity") -> list[Finding]:
    """Scan log and json/jsonl files for internal tool invocations."""
    findings: list[Finding] = []
    if not base_dir.exists():
        return findings

    target_files: list[Path] = []
    for ext in ("*.log", "*.json", "*.jsonl"):
        target_files.extend(base_dir.rglob(ext))

    for file_path in target_files:
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for line_idx, line in enumerate(content.splitlines(), start=1):
            for match in ANTIGRAVITY_TOOL_PATTERN.finditer(line):
                tool_name = match.group(1)
                findings.append(
                    Finding(
                        name=tool_name,
                        kind="Internal Tool",
                        provider=provider,
                        file_path=file_path,
                        line_number=line_idx,
                        context=line.strip()[:200],
                    )
                )
    return findings


def scan_copilot_sessions(base_dir: Path) -> list[Finding]:
    """Scan GitHub Copilot VS Code chat session JSON files for shell commands and tools."""
    findings: list[Finding] = []
    if not base_dir.exists():
        return findings

    json_files = list(base_dir.glob("*.json")) if base_dir.is_dir() else [base_dir]
    for file_path in json_files:
        if file_path.suffix.lower() != ".json":
            continue
        try:
            data = json.loads(file_path.read_text(encoding="utf-8", errors="replace"))
        except (json.JSONDecodeError, OSError):
            continue

        string_contents = extract_strings_from_json(data)
        for text in string_contents:
            for block in CODE_BLOCK_PATTERN.findall(text):
                for line in block.splitlines():
                    cmd_key = extract_command_key(line)
                    if cmd_key:
                        findings.append(
                            Finding(
                                name=cmd_key,
                                kind="CLI Command",
                                provider="GitHub Copilot",
                                file_path=file_path,
                                line_number=None,
                                context=line.strip()[:200],
                            )
                        )
    return findings


def scan_ollama_logs(base_dir: Path) -> list[Finding]:
    """Scan Ollama server logs for endpoint queries and model requests."""
    findings: list[Finding] = []
    if not base_dir.exists():
        return findings

    log_files = [base_dir] if base_dir.is_file() else list(base_dir.glob("*.log"))
    for log_file in log_files:
        try:
            content = log_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for line_idx, line in enumerate(content.splitlines(), start=1):
            match = OLLAMA_API_PATTERN.search(line)
            if match:
                endpoint = match.group(1)
                findings.append(
                    Finding(
                        name=f"ollama {endpoint}",
                        kind="LLM Endpoint",
                        provider="Ollama",
                        file_path=log_file,
                        line_number=line_idx,
                        context=line.strip()[:200],
                    )
                )
    return findings


def scan_claude_code(base_dir: Path) -> list[Finding]:
    """Scan Claude Code CLI directory for skills, markdown and JSON logs."""
    findings: list[Finding] = []
    if not base_dir.exists():
        return findings

    findings.extend(scan_markdown_artifacts(base_dir, provider="Claude Code"))
    findings.extend(scan_tool_logs(base_dir, provider="Claude Code"))
    return findings


def aggregate_findings(findings: list[Finding]) -> list[AuditEntry]:
    """Aggregate individual findings into a sorted list of AuditEntry objects."""
    grouped: dict[tuple[str, str, str], list[Finding]] = defaultdict(list)
    for finding in findings:
        grouped[(finding.name, finding.kind, finding.provider)].append(finding)

    entries = [
        AuditEntry(
            name=name,
            kind=kind,
            provider=provider,
            count=len(item_findings),
            findings=item_findings,
        )
        for (name, kind, provider), item_findings in grouped.items()
    ]
    entries.sort(key=lambda e: e.count, reverse=True)
    return entries


def scan_sources(
    sources: list[tuple[Path, str]],
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[AuditEntry]:
    """Scan multiple directory sources and aggregate the audit findings."""
    all_findings: list[Finding] = []
    total = len(sources)

    for idx, (path, provider) in enumerate(sources, start=1):
        if progress_callback:
            progress_callback(idx, total, f"Scanning {provider}: {path.name}")

        if not path.exists():
            continue

        if provider == "Claude Desktop":
            all_findings.extend(scan_claude_logs(path))
        elif provider == "Antigravity":
            all_findings.extend(scan_markdown_artifacts(path, provider="Antigravity"))
            all_findings.extend(scan_tool_logs(path, provider="Antigravity"))
        elif provider == "GitHub Copilot":
            all_findings.extend(scan_copilot_sessions(path))
        elif provider == "Ollama":
            all_findings.extend(scan_ollama_logs(path))
        elif provider == "Claude Code":
            all_findings.extend(scan_claude_code(path))
        else:
            # Custom Workspace or generic directory
            all_findings.extend(scan_markdown_artifacts(path, provider=provider))
            all_findings.extend(scan_tool_logs(path, provider=provider))

    return aggregate_findings(all_findings)


def generate_skill_markdown(entry: AuditEntry) -> str:
    """Generate a clean SKILL.md template from an audit entry for future agent reuse."""
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", entry.name.lower()).strip("-")
    if not slug:
        slug = "custom-agent-skill"

    sample_contexts: list[str] = []
    for f in entry.findings[:5]:
        line_ref = f":L{f.line_number}" if f.line_number else ""
        sample_contexts.append(f"- `{f.file_path.name}{line_ref}`: {f.context}")
    context_block = (
        "\n".join(sample_contexts) if sample_contexts else "- Keine Detailzeilen erfasst."
    )

    return f"""---
name: {slug}
description: Automates recurring '{entry.name}' workflow discovered by py-agent-audit.
---

# {entry.name} Workflow

## Overview
This skill automates the recurring action `{entry.name}` (Category: `{entry.kind}`, Provider: `{entry.provider}`), which was called {entry.count} times in recorded agent workflows.

## Recommended Command
```bash
{entry.name}
```

## Discovery Context
- **Provider**: {entry.provider}
- **Category**: {entry.kind}
- **Recorded Occurrences**: {entry.count}x

### Top Log References
{context_block}
"""
