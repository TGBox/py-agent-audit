import json
from pathlib import Path

from src.mcp_installer import (
    SERVER_NAME,
    install_to_claude_desktop,
    is_installed_in_claude_desktop,
)


def test_install_to_empty_config(tmp_path: Path):
    config_file = tmp_path / "claude" / "claude_desktop_config.json"
    project_dir = tmp_path / "py-agent-audit"
    project_dir.mkdir()

    assert not is_installed_in_claude_desktop(config_file)

    success, msg = install_to_claude_desktop(config_path=config_file, project_dir=project_dir)
    assert success
    assert "erfolgreich" in msg
    assert config_file.exists()
    assert is_installed_in_claude_desktop(config_file)

    data = json.loads(config_file.read_text(encoding="utf-8"))
    assert SERVER_NAME in data["mcpServers"]
    entry = data["mcpServers"][SERVER_NAME]
    assert entry["command"] == "uv"
    assert entry["args"] == [
        "run",
        "--directory",
        str(project_dir.resolve()),
        "py-agent-audit-server",
    ]


def test_install_preserves_existing_servers_and_creates_backup(tmp_path: Path):
    config_file = tmp_path / "claude_desktop_config.json"
    initial_content = {
        "mcpServers": {
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem"],
            }
        }
    }
    config_file.write_text(json.dumps(initial_content), encoding="utf-8")

    success, _msg = install_to_claude_desktop(config_path=config_file, project_dir=tmp_path)
    assert success

    # Verify backup exists
    backup_file = config_file.with_suffix(".json.bak")
    assert backup_file.exists()
    backup_data = json.loads(backup_file.read_text(encoding="utf-8"))
    assert "filesystem" in backup_data["mcpServers"]
    assert SERVER_NAME not in backup_data["mcpServers"]

    # Verify current file has BOTH servers
    current_data = json.loads(config_file.read_text(encoding="utf-8"))
    assert "filesystem" in current_data["mcpServers"]
    assert SERVER_NAME in current_data["mcpServers"]
