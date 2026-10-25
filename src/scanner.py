"""Scanner module for auditing AI coding agent logs and artifacts."""

import os
import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

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


@dataclass(slots=True)
class Finding:
    """Represents a single occurrence of a command or tool usage."""

    name: str
    kind: str  # e.g., 'CLI Command', 'MCP Tool', 'Internal Tool'
    provider: str  # e.g., 'Claude Desktop', 'Antigravity', 'Workspace'
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


def get_default_search_paths() -> dict[str, list[Path]]:
    """Return default search directories per provider based on OS environment."""
    appdata = Path(os.environ.get("APPDATA", ""))
    userprofile = Path(os.environ.get("USERPROFILE", Path.home()))

    paths: dict[str, list[Path]] = {
        "Claude Desktop": [],
        "Antigravity": [],
    }

    claude_log_dir = appdata / "Claude" / "logs"
    if claude_log_dir.exists():
        paths["Claude Desktop"].append(claude_log_dir)

    ag_candidates = [
        userprofile / ".gemini" / "antigravity",
        userprofile / ".gemini" / "antigravity-ide",
        appdata / "Antigravity" / "logs",
    ]
    for candidate in ag_candidates:
        if candidate.exists():
            paths["Antigravity"].append(candidate)

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
        else:
            # Custom Workspace or generic directory
            all_findings.extend(scan_markdown_artifacts(path, provider=provider))
            all_findings.extend(scan_tool_logs(path, provider=provider))

    return aggregate_findings(all_findings)
