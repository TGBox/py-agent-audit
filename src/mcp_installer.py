"""Helper for registering the TokenOptimizer MCP server in Claude Desktop config."""

import json
import os
import shutil
from pathlib import Path

SERVER_NAME = "py-agent-audit-optimizer"


def get_claude_desktop_config_path() -> Path:
    """Return the platform-specific path to Claude Desktop's configuration file."""
    appdata = Path(os.environ.get("APPDATA", ""))
    return appdata / "Claude" / "claude_desktop_config.json"


def is_installed_in_claude_desktop(config_path: Path | None = None) -> bool:
    """Check if py-agent-audit-optimizer is registered in claude_desktop_config.json."""
    path = config_path or get_claude_desktop_config_path()
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        servers = data.get("mcpServers", {})
        return SERVER_NAME in servers
    except (json.JSONDecodeError, OSError):
        return False


def install_to_claude_desktop(
    config_path: Path | None = None,
    project_dir: Path | None = None,
) -> tuple[bool, str]:
    """Register the TokenOptimizer server into claude_desktop_config.json safely.

    Preserves all existing MCP servers and creates an atomic backup before writing.
    Returns (success: bool, message: str).
    """
    path = config_path or get_claude_desktop_config_path()
    proj = project_dir or Path.cwd()

    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        data: dict = {}
        if path.is_file():
            # Create a backup before editing
            backup_path = path.with_suffix(".json.bak")
            shutil.copy2(path, backup_path)
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}

        if not isinstance(data, dict):
            data = {}

        if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
            data["mcpServers"] = {}

        data["mcpServers"][SERVER_NAME] = {
            "command": "uv",
            "args": [
                "run",
                "--directory",
                str(proj.resolve()),
                "py-agent-audit-server",
            ],
        }

        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return (
            True,
            f"Server '{SERVER_NAME}' wurde erfolgreich in Claude Desktop registriert:\n{path}",
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"Fehler beim Konfigurieren von Claude Desktop: {exc}"
