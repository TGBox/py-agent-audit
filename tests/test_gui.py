import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

# Ensure headless execution for tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from src.gui import MainWindow, ScanWorker
from src.scanner import AuditEntry, Finding


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_main_window_init(qapp):
    window = MainWindow()
    assert "py-agent-audit" in window.windowTitle()
    assert window.table.columnCount() == 4
    assert window.table.rowCount() == 0
    assert window.shortcut_f11 is not None

    # Check multi-source checkboxes
    assert window.cb_claude is not None
    assert window.cb_antigravity is not None
    assert window.cb_copilot is not None
    assert window.cb_ollama is not None
    assert window.cb_claude_code is not None
    assert window.cb_bottlenecks is not None
    assert not window.btn_export_skill.isEnabled()

    # Check MCP installer button and detailed polyglot tooltip
    assert window.btn_install_mcp is not None
    assert "MCP-Server" in window.btn_install_mcp.text()
    tooltip = window.btn_install_mcp.toolTip()
    assert "TokenOptimizer" in tooltip
    assert "run_compact_checks" in tooltip
    assert "read_code_signatures" in tooltip
    assert "read_python_signatures" in tooltip
    assert "Rust" in tooltip
    assert "get_compact_git_diff" in tooltip
    assert "get_project_tree" in tooltip
    assert "log_bottleneck" in tooltip


def test_main_window_toggle_fullscreen(qapp):
    window = MainWindow()
    assert not window.isFullScreen()

    window.toggle_fullscreen()
    assert window.isFullScreen()

    window.toggle_fullscreen()
    assert not window.isFullScreen()


def test_main_window_apply_filter(qapp):
    window = MainWindow()

    entry1 = AuditEntry(
        name="pytest tests/",
        kind="CLI Command",
        provider="Workspace",
        count=5,
        findings=[
            Finding(
                "pytest tests/", "CLI Command", "Workspace", Path("test.md"), 10, "pytest tests/"
            )
        ],
    )
    entry2 = AuditEntry(
        name="read_resource",
        kind="MCP Tool",
        provider="Claude Desktop",
        count=12,
        findings=[Finding("read_resource", "MCP Tool", "Claude Desktop", Path("mcp.log"), 1)],
    )

    window.entries = [entry1, entry2]
    window.apply_filter()

    assert window.table.rowCount() == 2

    # Filter by name
    window.search_input.setText("pytest")
    assert window.table.rowCount() == 1
    assert window.table.item(0, 0).text() == "pytest tests/"

    # Reset search
    window.search_input.setText("")
    assert window.table.rowCount() == 2

    # Filter by kind
    window.combo_kind.setCurrentText("MCP Tool")
    assert window.table.rowCount() == 1
    assert window.table.item(0, 0).text() == "read_resource"


def test_main_window_selection_detail_and_skill_button(qapp):
    window = MainWindow()

    entry = AuditEntry(
        name="git status",
        kind="CLI Command",
        provider="Workspace",
        count=3,
        findings=[
            Finding("git status", "CLI Command", "Workspace", Path("notes.md"), 5, "git status"),
            Finding("git status", "CLI Command", "Workspace", Path("run.md"), 8, "git status"),
        ],
    )
    window.entries = [entry]
    window.apply_filter()

    assert window.table.rowCount() == 1
    assert not window.btn_export_skill.isEnabled()

    window.table.selectRow(0)

    assert "git status" in window.lbl_detail_title.text()
    assert "notes.md:L5" in window.detail_text.toPlainText()
    assert "run.md:L8" in window.detail_text.toPlainText()
    assert window.btn_export_skill.isEnabled()
    assert window.selected_entry == entry


def test_scan_worker_emits_cancelled_instead_of_results(qapp, tmp_path: Path):
    (tmp_path / "plan.md").write_text("```sh\npytest -v\n```", encoding="utf-8")
    worker = ScanWorker([(tmp_path, "Workspace")])
    done: list = []
    cancelled: list = []
    worker.scan_done.connect(done.append)
    worker.cancelled.connect(lambda: cancelled.append(True))

    worker.cancel()
    worker.run()  # run synchronously in the test thread

    assert cancelled == [True]
    assert done == []


def test_cancel_does_not_block_and_resets_on_cancelled(qapp):
    window = MainWindow()
    window.on_scan_cancelled()
    assert window.btn_scan.isEnabled()
    assert window.btn_scan.text() == "Scan starten"
    assert "abgebrochen" in window.status_label.text()
