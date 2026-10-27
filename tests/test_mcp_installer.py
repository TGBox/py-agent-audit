import json
from pathlib import Path

from src.mcp_installer import (
    PACKAGE_PROJECT_DIR,
    SERVER_NAME,
    install_to_claude_desktop,
    is_installed_in_claude_desktop,
)


def test_install_to_empty_config(tmp_path: Path):
    config_file = tmp_path / "claude" / "claude_desktop_config.json"
    project_dir = tmp_path / "py-agent-audit"
    project_dir.mkdir()
    (project_dir / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

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
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

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


def test_install_does_not_overwrite_invalid_config(tmp_path: Path):
    config_file = tmp_path / "claude_desktop_config.json"
    broken = '{"mcpServers": {"filesystem": {"command": "npx",}}'  # trailing comma
    config_file.write_text(broken, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

    success, msg = install_to_claude_desktop(config_path=config_file, project_dir=tmp_path)
    assert not success
    assert "nicht verändert" in msg
    assert config_file.read_text(encoding="utf-8") == broken


def test_install_rejects_directory_without_pyproject(tmp_path: Path):
    config_file = tmp_path / "claude_desktop_config.json"
    success, msg = install_to_claude_desktop(config_path=config_file, project_dir=tmp_path)
    assert not success
    assert "pyproject.toml" in msg
    assert not config_file.exists()


def test_default_project_dir_is_package_checkout_not_cwd(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "claude_desktop_config.json"
    success, _msg = install_to_claude_desktop(config_path=config_file)
    assert success
    args = json.loads(config_file.read_text(encoding="utf-8"))["mcpServers"][SERVER_NAME]["args"]
    assert args[2] == str(PACKAGE_PROJECT_DIR)
    assert (PACKAGE_PROJECT_DIR / "pyproject.toml").is_file()
