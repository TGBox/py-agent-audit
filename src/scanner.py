"""Scanner module for auditing AI coding agent logs, artifacts, and multi-source workflows."""

import json
import os
import re
import zipfile
from collections import defaultdict
from collections.abc import Callable, Iterator
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
# Separators between chained shell commands ("a && b", "a; b", "a || b", "a | b")
SHELL_CHAIN_PATTERN = re.compile(r"\s*(?:&&|\|\||;|\|)\s*")

CancelCheck = Callable[[], bool]


class ScanCancelled(Exception):
    """Raised when a running scan was cancelled by the user."""


def _check_cancel(should_cancel: CancelCheck | None) -> None:
    if should_cancel is not None and should_cancel():
        raise ScanCancelled


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


def _env_path(name: str, default: Path | None = None) -> Path | None:
    """Return an environment variable as Path, or default if unset/empty.

    Path("") would silently resolve relative to the CWD, so empty values are rejected.
    """
    value = os.environ.get(name, "").strip()
    return Path(value) if value else default


def get_claude_desktop_data_dirs() -> list[Path]:
    """Return existing Claude Desktop data directories, most specific first.

    The Microsoft Store / MSIX build of Claude Desktop does not write to %APPDATA%\\Claude.
    Windows redirects its AppData writes into the package folder:
    %LOCALAPPDATA%\\Packages\\Claude_<publisher-id>\\LocalCache\\Roaming\\Claude
    Other processes (like this scanner) still see the real, often empty %APPDATA%\\Claude.
    """
    candidates: list[Path] = []
    localappdata = _env_path("LOCALAPPDATA")
    if localappdata is not None:
        packages = localappdata / "Packages"
        if packages.is_dir():
            for package in sorted(packages.glob("Claude_*")):
                candidates.append(package / "LocalCache" / "Roaming" / "Claude")
    appdata = _env_path("APPDATA")
    if appdata is not None:
        candidates.append(appdata / "Claude")

    result: list[Path] = []
    for candidate in candidates:
        if candidate.is_dir() and candidate not in result:
            result.append(candidate)
    return result


def get_claude_code_dirs() -> list[Path]:
    """Return existing Claude Code config directories (CLAUDE_CONFIG_DIR, then ~/.claude)."""
    candidates = [
        p
        for p in (
            _env_path("CLAUDE_CONFIG_DIR"),
            _env_path("USERPROFILE", Path.home()) / ".claude",
            Path.home() / ".claude",
        )
        if p is not None
    ]
    result: list[Path] = []
    for candidate in candidates:
        if candidate.is_dir() and candidate not in result:
            result.append(candidate)
    return result


def get_default_search_paths() -> dict[str, list[Path]]:
    """Return default search directories per provider based on OS environment."""
    home = Path.home()
    appdata = _env_path("APPDATA", home / "AppData" / "Roaming")
    localappdata = _env_path("LOCALAPPDATA", home / "AppData" / "Local")
    userprofile = _env_path("USERPROFILE", home)

    paths: dict[str, list[Path]] = {
        "Claude Desktop": [],
        "Antigravity": [],
        "GitHub Copilot": [],
        "Ollama": [],
        "Claude Code": [],
    }

    # Claude Desktop (regular installer and Microsoft Store / MSIX build)
    for data_dir in get_claude_desktop_data_dirs():
        claude_log_dir = data_dir / "logs"
        if claude_log_dir.is_dir():
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
    paths["Claude Code"].extend(get_claude_code_dirs())

    # TokenOptimizer Bottlenecks
    bottleneck_log = userprofile / ".mcp_bottlenecks.jsonl"
    if bottleneck_log.exists():
        paths["TokenOptimizer"] = [bottleneck_log]

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


def scan_markdown_artifacts(
    base_dir: Path,
    provider: str = "Workspace",
    should_cancel: CancelCheck | None = None,
) -> list[Finding]:
    """Scan markdown files for shell commands inside code blocks."""
    findings: list[Finding] = []
    if not base_dir.exists():
        return findings

    for md_file in base_dir.rglob("*.md"):
        _check_cancel(should_cancel)
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


def scan_tool_logs(
    base_dir: Path,
    provider: str = "Antigravity",
    should_cancel: CancelCheck | None = None,
) -> list[Finding]:
    """Scan log and json/jsonl files for internal tool invocations."""
    findings: list[Finding] = []
    if not base_dir.exists():
        return findings

    target_files: list[Path] = []
    for ext in ("*.log", "*.json", "*.jsonl"):
        target_files.extend(base_dir.rglob(ext))

    for file_path in target_files:
        _check_cancel(should_cancel)
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


def split_shell_commands(command: str) -> list[str]:
    """Split a (possibly multi-line or chained) shell command into single commands."""
    parts: list[str] = []
    for line in command.splitlines():
        parts.extend(p for p in SHELL_CHAIN_PATTERN.split(line) if p.strip())
    return parts


def _tool_use_blocks(record: Any) -> list[dict[str, Any]]:
    """Return all tool_use blocks of one Claude Code transcript record."""
    if not isinstance(record, dict):
        return []
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return []
    return [
        block
        for block in content
        if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name")
    ]


def scan_claude_code_sessions(
    base_dir: Path, should_cancel: CancelCheck | None = None
) -> list[Finding]:
    """Scan Claude Code session transcripts (~/.claude/projects/**/*.jsonl) for tool calls.

    Every ``tool_use`` block becomes a finding: ``Bash`` commands are split into single
    shell commands (kind ``CLI Command``), ``mcp__*`` tools are ``MCP Tool`` and all other
    built-in tools (Read, Edit, Grep, ...) are ``Internal Tool``.
    """
    findings: list[Finding] = []
    projects_dir = base_dir / "projects"
    search_root = projects_dir if projects_dir.is_dir() else base_dir
    if not search_root.exists():
        return findings

    for file_path in search_root.rglob("*.jsonl"):
        _check_cancel(should_cancel)
        try:
            handle = file_path.open(encoding="utf-8", errors="replace")
        except OSError:
            continue
        with handle:
            for line_idx, line in enumerate(handle, start=1):
                if '"tool_use"' not in line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for block in _tool_use_blocks(record):
                    findings.extend(_findings_from_tool_use(block, file_path, line_idx))
    return findings


# Tool names whose "command" input is a shell command line
SHELL_TOOL_NAMES = {"Bash", "bash", "bash_tool", "PowerShell", "powershell", "run_command"}


def _findings_from_tool_use(
    block: dict[str, Any],
    file_path: Path,
    line_idx: int | None,
    provider: str = "Claude Code",
    context_prefix: str = "",
) -> list[Finding]:
    tool_name = str(block["name"])
    tool_input = block.get("input") if isinstance(block.get("input"), dict) else {}

    if tool_name in SHELL_TOOL_NAMES and isinstance(tool_input.get("command"), str):
        result: list[Finding] = []
        for command in split_shell_commands(tool_input["command"]):
            cmd_key = extract_command_key(command)
            if cmd_key:
                result.append(
                    Finding(
                        name=cmd_key,
                        kind="CLI Command",
                        provider=provider,
                        file_path=file_path,
                        line_number=line_idx,
                        context=(context_prefix + command.strip())[:200],
                    )
                )
        return result

    kind = "MCP Tool" if tool_name.startswith("mcp__") else "Internal Tool"
    context = context_prefix + json.dumps(tool_input, ensure_ascii=False)
    return [
        Finding(
            name=tool_name,
            kind=kind,
            provider=provider,
            file_path=file_path,
            line_number=line_idx,
            context=context[:200],
        )
    ]


def scan_claude_code(base_dir: Path, should_cancel: CancelCheck | None = None) -> list[Finding]:
    """Scan the Claude Code CLI directory (~/.claude) for executed tool calls.

    Only real session transcripts are evaluated. Markdown files below ~/.claude (skills,
    plugin docs) merely mention commands and are therefore not counted.
    """
    if not base_dir.exists():
        return []
    return scan_claude_code_sessions(base_dir, should_cancel=should_cancel)


def _iter_export_documents(
    path: Path, should_cancel: CancelCheck | None = None
) -> Iterator[tuple[Path, Any]]:
    """Yield (file, parsed JSON) for a claude.ai export: ZIP, JSON file or extracted folder."""
    if path.is_dir():
        for json_file in sorted(path.rglob("*.json")):
            _check_cancel(should_cancel)
            try:
                yield json_file, json.loads(json_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                continue
    elif path.suffix.lower() == ".zip":
        try:
            archive = zipfile.ZipFile(path)
        except (OSError, zipfile.BadZipFile):
            return
        with archive:
            for member in archive.namelist():
                _check_cancel(should_cancel)
                if not member.lower().endswith(".json"):
                    continue
                try:
                    data = json.loads(archive.read(member).decode("utf-8"))
                except (OSError, json.JSONDecodeError, UnicodeDecodeError, KeyError):
                    continue
                yield path / member, data
    elif path.suffix.lower() == ".json":
        try:
            yield path, json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return


def _walk_tool_uses(data: Any, conversation: str = "") -> Iterator[tuple[dict[str, Any], str]]:
    """Recursively yield (tool_use block, conversation title) from arbitrary JSON.

    The export format is not documented, so instead of relying on a fixed schema every
    nested ``{"type": "tool_use", "name": ...}`` object is collected.
    """
    stack: list[tuple[Any, str]] = [(data, conversation)]
    while stack:
        node, title = stack.pop()
        if isinstance(node, dict):
            if node.get("type") == "tool_use" and node.get("name"):
                yield node, title
                continue
            # A conversation object carries its title next to its messages
            if isinstance(node.get("name"), str) and any(
                key in node for key in ("chat_messages", "messages")
            ):
                title = node["name"]
            stack.extend((value, title) for value in reversed(list(node.values())))
        elif isinstance(node, list):
            stack.extend((item, title) for item in reversed(node))


def scan_claude_export(path: Path, should_cancel: CancelCheck | None = None) -> list[Finding]:
    """Scan a claude.ai data export (Settings > Privacy > Export data) for tool calls.

    Accepts the downloaded ZIP, an extracted folder or a single JSON file such as
    conversations.json. Chats in the Claude app are stored in the cloud, so this export
    is the only local source for them.
    """
    findings: list[Finding] = []
    if not path.exists():
        return findings
    for file_path, data in _iter_export_documents(path, should_cancel):
        for block, title in _walk_tool_uses(data):
            prefix = f"[{title}] " if title else ""
            findings.extend(
                _findings_from_tool_use(
                    block, file_path, None, provider="Claude App", context_prefix=prefix
                )
            )
    return findings


def scan_bottleneck_logs(log_path: Path) -> list[Finding]:
    """Scan ~/.mcp_bottlenecks.jsonl for agent-reported routine bottlenecks."""
    findings: list[Finding] = []
    target_files = [log_path] if log_path.is_file() else list(log_path.glob("*.jsonl"))
    for file_path in target_files:
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for line_idx, line in enumerate(content.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                task = data.get("task", "Unbekannte Aufgabe")
                steps = data.get("steps", 0)
                reason = data.get("reason", "")
                findings.append(
                    Finding(
                        name=f"Bottleneck: {task}",
                        kind="Agent Bottleneck",
                        provider="TokenOptimizer",
                        file_path=file_path,
                        line_number=line_idx,
                        context=f"{steps} Schritte | Grund: {reason}"[:200],
                    )
                )
            except json.JSONDecodeError:
                continue
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
    should_cancel: CancelCheck | None = None,
) -> list[AuditEntry]:
    """Scan multiple directory sources and aggregate the audit findings.

    Raises ScanCancelled as soon as ``should_cancel`` returns True.
    """
    all_findings: list[Finding] = []
    total = len(sources)

    for idx, (path, provider) in enumerate(sources, start=1):
        _check_cancel(should_cancel)
        if progress_callback:
            progress_callback(idx, total, f"Scanning {provider}: {path.name}")

        if not path.exists():
            continue

        if provider == "Claude Desktop":
            all_findings.extend(scan_claude_logs(path))
        elif provider == "Antigravity":
            all_findings.extend(
                scan_markdown_artifacts(path, provider="Antigravity", should_cancel=should_cancel)
            )
            all_findings.extend(
                scan_tool_logs(path, provider="Antigravity", should_cancel=should_cancel)
            )
        elif provider == "GitHub Copilot":
            all_findings.extend(scan_copilot_sessions(path))
        elif provider == "Ollama":
            all_findings.extend(scan_ollama_logs(path))
        elif provider == "Claude Code":
            all_findings.extend(scan_claude_code(path, should_cancel=should_cancel))
        elif provider == "Claude App":
            all_findings.extend(scan_claude_export(path, should_cancel=should_cancel))
        elif provider == "TokenOptimizer":
            all_findings.extend(scan_bottleneck_logs(path))
        else:
            # Custom Workspace or generic directory
            all_findings.extend(
                scan_markdown_artifacts(path, provider=provider, should_cancel=should_cancel)
            )
            all_findings.extend(
                scan_tool_logs(path, provider=provider, should_cancel=should_cancel)
            )

    _check_cancel(should_cancel)
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

    # JSON strings are valid double-quoted YAML scalars, so ':' or quotes in the name
    # (e.g. "Bottleneck: ...") can no longer break the frontmatter.
    description = json.dumps(
        f"Automates recurring '{entry.name}' workflow discovered by py-agent-audit.",
        ensure_ascii=False,
    )

    return f"""---
name: {slug}
description: {description}
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
