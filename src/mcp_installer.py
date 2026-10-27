"""Helper for registering the TokenOptimizer MCP server in Claude Desktop config."""

import json
import os
import shutil
import tempfile
from pathlib import Path

from src.scanner import get_claude_desktop_data_dirs

SERVER_NAME = "py-agent-audit-optimizer"
CONFIG_FILENAME = "claude_desktop_config.json"

# Project root of this checkout (src/mcp_installer.py -> project root), independent of CWD.
PACKAGE_PROJECT_DIR = Path(__file__).resolve().parent.parent


def get_claude_desktop_config_path() -> Path:
    """Return the path to Claude Desktop's configuration file.

    Prefers the Microsoft Store / MSIX data folder (the only one that build reads),
    falls back to %APPDATA%\\Claude for the regular installer.
    """
    data_dirs = get_claude_desktop_data_dirs()
    if data_dirs:
        return data_dirs[0] / CONFIG_FILENAME
    appdata = os.environ.get("APPDATA", "").strip()
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / "Claude" / CONFIG_FILENAME


def is_installed_in_claude_desktop(config_path: Path | None = None) -> bool:
    """Check if py-agent-audit-optimizer is registered in claude_desktop_config.json."""
    path = config_path or get_claude_desktop_config_path()
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        servers = data.get("mcpServers", {})
        return SERVER_NAME in servers
    except (json.JSONDecodeError, OSError, AttributeError):
        return False


def _write_json_atomically(path: Path, data: dict) -> None:
    """Write JSON to a temp file in the same directory and atomically replace the target."""
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def install_to_claude_desktop(
    config_path: Path | None = None,
    project_dir: Path | None = None,
) -> tuple[bool, str]:
    """Register the TokenOptimizer server into claude_desktop_config.json safely.

    Preserves all existing MCP servers, creates a backup and writes atomically.
    An existing but unreadable/invalid config is never overwritten.
    Returns (success: bool, message: str).
    """
    path = config_path or get_claude_desktop_config_path()
    proj = (project_dir or PACKAGE_PROJECT_DIR).resolve()

    if not (proj / "pyproject.toml").is_file():
        return (
            False,
            "Projektverzeichnis von py-agent-audit nicht gefunden "
            f"(keine pyproject.toml in '{proj}').\n"
            "Die Installation funktioniert nur aus einem Quellcode-Checkout mit uv, "
            "nicht aus der gebauten Exe.",
        )

    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        data: dict = {}
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                return (
                    False,
                    f"Die bestehende Konfiguration ist kein gültiges JSON und wurde nicht "
                    f"verändert:\n{path}\n\n{exc}",
                )
            if not isinstance(data, dict):
                return (
                    False,
                    f"Unerwartetes Format der bestehenden Konfiguration (kein JSON-Objekt), "
                    f"Datei wurde nicht verändert:\n{path}",
                )
            # Create a backup before editing
            shutil.copy2(path, path.with_suffix(".json.bak"))

        if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
            data["mcpServers"] = {}

        data["mcpServers"][SERVER_NAME] = {
            "command": "uv",
            "args": [
                "run",
                "--directory",
                str(proj),
                "py-agent-audit-server",
            ],
        }

        _write_json_atomically(path, data)
        return (
            True,
            f"Server '{SERVER_NAME}' wurde erfolgreich in Claude Desktop registriert:\n{path}",
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"Fehler beim Konfigurieren von Claude Desktop: {exc}"
