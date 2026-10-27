"""PySide6 graphical user interface for the AI Agent Audit application."""

import re
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.mcp_installer import install_to_claude_desktop, is_installed_in_claude_desktop
from src.scanner import (
    AuditEntry,
    ScanCancelled,
    generate_skill_markdown,
    get_default_search_paths,
    scan_sources,
)

DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    font-size: 13px;
}

QGroupBox {
    border: 1px solid #45475a;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: bold;
    color: #89b4fa;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
}

QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #45475a;
    border-color: #89b4fa;
}

QPushButton:pressed {
    background-color: #585b70;
}

QPushButton#primaryBtn {
    background-color: #89b4fa;
    color: #11111b;
    font-weight: bold;
    border: none;
}

QPushButton#primaryBtn:hover {
    background-color: #b4befe;
}

QPushButton#primaryBtn:disabled {
    background-color: #45475a;
    color: #7f849c;
}

QPushButton#actionBtn {
    background-color: #a6e3a1;
    color: #11111b;
    font-weight: bold;
    border: none;
}

QPushButton#actionBtn:hover {
    background-color: #94e2d5;
}

QPushButton#installBtn {
    background-color: #262738;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 3px 10px;
    font-size: 11px;
}

QPushButton#installBtn:hover {
    background-color: #313244;
    border-color: #89b4fa;
    color: #ffffff;
}

QLineEdit, QComboBox {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 5px 8px;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #89b4fa;
}

QTableWidget {
    background-color: #181825;
    color: #cdd6f4;
    gridline-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    selection-background-color: #45475a;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #313244;
    color: #cdd6f4;
    padding: 5px;
    border: 1px solid #45475a;
    font-weight: bold;
}

QProgressBar {
    background-color: #181825;
    border: 1px solid #45475a;
    border-radius: 4px;
    text-align: center;
    color: #cdd6f4;
    font-weight: bold;
}

QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 3px;
}

QTextEdit {
    background-color: #11111b;
    color: #a6adc8;
    border: 1px solid #45475a;
    border-radius: 4px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
}

QCheckBox {
    spacing: 6px;
    color: #cdd6f4;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #45475a;
    background-color: #181825;
}

QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}
"""


class ScanWorker(QThread):
    """Background worker thread for non-blocking log scanning."""

    progress = Signal(int, int, str)
    # Named scan_done (not "finished") to avoid shadowing QThread's built-in finished signal.
    scan_done = Signal(list)
    cancelled = Signal()
    failed = Signal(str)

    def __init__(self, sources: list[tuple[Path, str]]) -> None:
        super().__init__()
        self.sources = sources
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def run(self) -> None:
        try:

            def callback(current: int, total: int, msg: str) -> None:
                if not self._is_cancelled:
                    self.progress.emit(current, total, msg)

            results = scan_sources(
                self.sources, progress_callback=callback, should_cancel=self.is_cancelled
            )
            self.scan_done.emit(results)
        except ScanCancelled:
            self.cancelled.emit()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    """Main window of the py-agent-audit application."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("py-agent-audit — Multi-Source Agent Audit & TokenOptimizer")
        self.setMinimumSize(1020, 680)

        self.entries: list[AuditEntry] = []
        self.worker: ScanWorker | None = None
        self.custom_paths: list[Path] = []
        self.selected_entry: AuditEntry | None = None

        self.init_ui()
        self.load_settings()
        self.setup_shortcuts()

    def init_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # 1. Source configuration box
        sources_group = QGroupBox("Erkannte KI-Quellen & Agenten-Pfade")
        sources_layout = QHBoxLayout(sources_group)

        default_paths = get_default_search_paths()
        has_claude = bool(default_paths.get("Claude Desktop"))
        has_ag = bool(default_paths.get("Antigravity"))
        has_copilot = bool(default_paths.get("GitHub Copilot"))
        has_ollama = bool(default_paths.get("Ollama"))
        has_claude_code = bool(default_paths.get("Claude Code"))
        has_bottlenecks = bool(default_paths.get("TokenOptimizer"))

        self.cb_claude = QCheckBox(f"Claude Desktop ({'✓' if has_claude else '–'})")
        self.cb_claude.setChecked(has_claude)
        sources_layout.addWidget(self.cb_claude)

        self.cb_antigravity = QCheckBox(f"Antigravity ({'✓' if has_ag else '–'})")
        self.cb_antigravity.setChecked(has_ag)
        sources_layout.addWidget(self.cb_antigravity)

        self.cb_copilot = QCheckBox(f"GitHub Copilot ({'✓' if has_copilot else '–'})")
        self.cb_copilot.setChecked(has_copilot)
        sources_layout.addWidget(self.cb_copilot)

        self.cb_ollama = QCheckBox(f"Ollama ({'✓' if has_ollama else '–'})")
        self.cb_ollama.setChecked(has_ollama)
        sources_layout.addWidget(self.cb_ollama)

        self.cb_claude_code = QCheckBox(f"Claude Code ({'✓' if has_claude_code else '–'})")
        self.cb_claude_code.setChecked(has_claude_code)
        sources_layout.addWidget(self.cb_claude_code)

        self.cb_bottlenecks = QCheckBox(f"Engpässe ({'✓' if has_bottlenecks else '–'})")
        self.cb_bottlenecks.setChecked(has_bottlenecks)
        self.cb_bottlenecks.setToolTip(
            "Analysiert vom Agenten gemeldete Routine-Engpässe aus ~/.mcp_bottlenecks.jsonl"
        )
        sources_layout.addWidget(self.cb_bottlenecks)

        self.btn_add_folder = QPushButton("Workspace-Ordner...")
        self.btn_add_folder.clicked.connect(self.add_custom_folder)
        sources_layout.addWidget(self.btn_add_folder)

        self.lbl_custom_count = QLabel("0 Ordner")
        self.lbl_custom_count.setStyleSheet("color: #a6adc8;")
        sources_layout.addWidget(self.lbl_custom_count)

        self.btn_scan = QPushButton("Scan starten")
        self.btn_scan.setObjectName("primaryBtn")
        self.btn_scan.clicked.connect(self.toggle_scan)
        sources_layout.addWidget(self.btn_scan)

        main_layout.addWidget(sources_group)

        # 2. Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)

        # 3. Filter bar
        filter_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Befehl, Tool oder Endpunkt filtern...")
        self.search_input.textChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.search_input, stretch=3)

        self.combo_kind = QComboBox()
        self.combo_kind.addItems(
            [
                "Alle Typen",
                "CLI Command",
                "MCP Tool",
                "Internal Tool",
                "LLM Endpoint",
                "Agent Bottleneck",
            ]
        )
        self.combo_kind.currentTextChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.combo_kind, stretch=1)

        self.combo_provider = QComboBox()
        self.combo_provider.addItems(
            [
                "Alle Quellen",
                "Claude Desktop",
                "Antigravity",
                "GitHub Copilot",
                "Ollama",
                "Claude Code",
                "TokenOptimizer",
                "Workspace",
            ]
        )
        self.combo_provider.currentTextChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.combo_provider, stretch=1)

        main_layout.addLayout(filter_layout)

        # 4. Main content splitter (Table on the left, Detail view on the right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Table widget
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Befehl / Tool", "Typ", "Quelle", "Aufrufe"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self.on_table_selection_changed)
        splitter.addWidget(self.table)

        # Detail Panel
        detail_frame = QFrame()
        detail_layout = QVBoxLayout(detail_frame)
        detail_layout.setContentsMargins(6, 0, 0, 0)

        header_detail_layout = QHBoxLayout()
        self.lbl_detail_title = QLabel("Kontext-Inspektion")
        self.lbl_detail_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #89b4fa;")
        header_detail_layout.addWidget(self.lbl_detail_title)
        header_detail_layout.addStretch()

        self.btn_export_skill = QPushButton("Als Skill exportieren (SKILL.md)...")
        self.btn_export_skill.setObjectName("actionBtn")
        self.btn_export_skill.setEnabled(False)
        self.btn_export_skill.clicked.connect(self.export_selected_as_skill)
        header_detail_layout.addWidget(self.btn_export_skill)

        detail_layout.addLayout(header_detail_layout)

        self.lbl_detail_subtitle = QLabel("Wähle einen Eintrag in der Tabelle aus.")
        self.lbl_detail_subtitle.setStyleSheet("color: #a6adc8; margin-bottom: 6px;")
        detail_layout.addWidget(self.lbl_detail_subtitle)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        detail_layout.addWidget(self.detail_text)

        splitter.addWidget(detail_frame)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter, stretch=1)

        # 5. Status bar & Footer actions (MCP-Server-Installation dezent abseits platziert)
        footer_layout = QHBoxLayout()
        self.status_label = QLabel("Bereit. Klicke auf 'Scan starten'.")
        self.status_label.setStyleSheet("color: #a6adc8; font-size: 12px;")
        footer_layout.addWidget(self.status_label)
        footer_layout.addStretch()

        is_installed = is_installed_in_claude_desktop()
        self.btn_install_mcp = QPushButton(
            "✓ MCP-Server in Claude aktiv"
            if is_installed
            else "MCP-Server in Claude Desktop installieren"
        )
        self.btn_install_mcp.setObjectName("installBtn")
        self.btn_install_mcp.setToolTip(
            "Registriert den TokenOptimizer FastMCP-Server in deiner lokalen Claude Desktop Konfiguration "
            "(%APPDATA%/Claude/claude_desktop_config.json).\n\n"
            "Folgende 5 polyglote Werkzeuge werden Claude zur Verfügung gestellt:\n"
            "• run_compact_checks: Erkennt automatisch Rust (cargo check), Node/TS (npm test / tsc), "
            ".NET (dotnet build) und Python (ruff / pytest) und liefert nur kompakte Fehlerzeilen\n"
            "• read_code_signatures: Spart 80–90% Tokens durch Lesen reiner Signaturen "
            "(Python, Rust, TypeScript/JS, C#) ohne Code-Bodies (Alias: read_python_signatures)\n"
            "• get_compact_git_diff: Kompaktes Git-Diff (U=0) ohne Lockfiles (Cargo, npm, uv) & Assets\n"
            "• get_project_tree: Bereinigter Projektbaum mit Zeilenzahlen (LOC) ohne Build-Ordner\n"
            "• log_bottleneck: Protokolliert wiederkehrende Agenten-Engpässe direkt nach ~/.mcp_bottlenecks.jsonl"
        )
        self.btn_install_mcp.clicked.connect(self.install_mcp_to_claude)
        footer_layout.addWidget(self.btn_install_mcp)

        main_layout.addLayout(footer_layout)

    def setup_shortcuts(self) -> None:
        """Register F11 shortcut for toggling fullscreen mode."""
        self.shortcut_f11 = QShortcut(QKeySequence("F11"), self)
        self.shortcut_f11.activated.connect(self.toggle_fullscreen)

        fullscreen_action = QAction("Vollbild umschalten (F11)", self)
        fullscreen_action.setShortcut(QKeySequence("F11"))
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        self.addAction(fullscreen_action)

    def toggle_fullscreen(self) -> None:
        """Toggle between windowed and fullscreen display modes."""
        if self.isFullScreen():
            self.showNormal()
            self.status_label.setText("Fenstermodus aktiv.")
        else:
            self.showFullScreen()
            self.status_label.setText("Vollbildmodus aktiv (F11 zum Beenden).")

    def add_custom_folder(self) -> None:
        """Open a directory chooser to add a custom workspace path."""
        folder = QFileDialog.getExistingDirectory(self, "Workspace-Ordner auswählen")
        if folder:
            path = Path(folder)
            if path not in self.custom_paths:
                self.custom_paths.append(path)
                count = len(self.custom_paths)
                self.lbl_custom_count.setText(f"{count} eigene{'r' if count == 1 else ''} Ordner")
                self.status_label.setText(f"Ordner hinzugefügt: {path}")

    def install_mcp_to_claude(self) -> None:
        """Install the TokenOptimizer FastMCP server into Claude Desktop config."""
        reply = QMessageBox.question(
            self,
            "TokenOptimizer MCP-Server in Claude Desktop installieren?",
            "Möchtest du den TokenOptimizer FastMCP-Server in deiner lokalen Claude Desktop Konfiguration eintragen?\n\n"
            "Folgende 5 polyglote Werkzeuge werden Claude bereitgestellt:\n"
            "1. run_compact_checks: Automatische Fehler-Prüfungen für Rust, Node/TS, .NET und Python\n"
            "2. read_code_signatures: Token-sparende Signaturen (Python, Rust, TS/JS, C#) ohne Rümpfe\n"
            "3. get_compact_git_diff: Kompaktes Git-Diff (U=0) ohne Lockfiles & Assets\n"
            "4. get_project_tree: Bereinigter Projektbaum mit Zeilenzahlen (LOC) ohne Build-Artefakte\n"
            "5. log_bottleneck: Protokollierung wiederkehrender Engpässe in ~/.mcp_bottlenecks.jsonl\n\n"
            "Bestehende MCP-Server bleiben erhalten. Es wird vor dem Speichern ein automatisches Backup (.bak) angelegt.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            success, msg = install_to_claude_desktop()
            if success:
                self.btn_install_mcp.setText("✓ MCP-Server in Claude aktiv")
                self.status_label.setText(
                    "TokenOptimizer MCP-Server erfolgreich in Claude Desktop installiert."
                )
                QMessageBox.information(self, "Installation erfolgreich", msg)
            else:
                self.status_label.setText("Fehler bei der Installation in Claude Desktop.")
                QMessageBox.critical(self, "Installationsfehler", msg)

    def toggle_scan(self) -> None:
        """Start or cancel the asynchronous scan process."""
        if self.worker and self.worker.isRunning():
            # Non-blocking: the worker stops at the next file and emits `cancelled`.
            self.worker.cancel()
            self.btn_scan.setEnabled(False)
            self.btn_scan.setText("Wird abgebrochen...")
            self.status_label.setText("Scan wird abgebrochen...")
            return

        sources: list[tuple[Path, str]] = []
        default_paths = get_default_search_paths()

        if self.cb_claude.isChecked():
            for p in default_paths.get("Claude Desktop", []):
                sources.append((p, "Claude Desktop"))

        if self.cb_antigravity.isChecked():
            for p in default_paths.get("Antigravity", []):
                sources.append((p, "Antigravity"))

        if self.cb_copilot.isChecked():
            for p in default_paths.get("GitHub Copilot", []):
                sources.append((p, "GitHub Copilot"))

        if self.cb_ollama.isChecked():
            for p in default_paths.get("Ollama", []):
                sources.append((p, "Ollama"))

        if self.cb_claude_code.isChecked():
            for p in default_paths.get("Claude Code", []):
                sources.append((p, "Claude Code"))

        if self.cb_bottlenecks.isChecked():
            for p in default_paths.get("TokenOptimizer", []):
                sources.append((p, "TokenOptimizer"))

        for p in self.custom_paths:
            sources.append((p, "Workspace"))

        if not sources:
            QMessageBox.warning(
                self,
                "Keine Quellen ausgewählt",
                "Bitte wähle mindestens eine Quelle aus oder füge einen Workspace-Ordner hinzu.",
            )
            return

        self.btn_scan.setText("Abbrechen")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(sources))
        self.status_label.setText("Scan läuft im Hintergrund...")

        self.worker = ScanWorker(sources)
        self.worker.progress.connect(self.on_scan_progress)
        self.worker.scan_done.connect(self.on_scan_finished)
        self.worker.cancelled.connect(self.on_scan_cancelled)
        self.worker.failed.connect(self.on_scan_failed)
        self.worker.start()

    def on_scan_progress(self, current: int, total: int, msg: str) -> None:
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(msg)

    def on_scan_finished(self, results: list[AuditEntry]) -> None:
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("Scan starten")
        self.progress_bar.setVisible(False)
        self.entries = results
        self.apply_filter()
        total_calls = sum(e.count for e in results)
        self.status_label.setText(
            f"Scan abgeschlossen: {len(results)} Aktionen ({total_calls} Aufrufe) gefunden."
        )

    def on_scan_cancelled(self) -> None:
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("Scan starten")
        self.progress_bar.setVisible(False)
        self.status_label.setText("Scan abgebrochen.")

    def on_scan_failed(self, error_msg: str) -> None:
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("Scan starten")
        self.progress_bar.setVisible(False)
        self.status_label.setText("Fehler beim Scan.")
        QMessageBox.critical(self, "Scan-Fehler", f"Fehler beim Scannen:\n{error_msg}")

    def apply_filter(self) -> None:
        """Filter table items based on search text, kind, and provider."""
        search_text = self.search_input.text().strip().lower()
        kind_filter = self.combo_kind.currentText()
        provider_filter = self.combo_provider.currentText()

        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        matching_entries: list[AuditEntry] = []
        for entry in self.entries:
            if search_text and search_text not in entry.name.lower():
                continue
            if kind_filter != "Alle Typen" and entry.kind != kind_filter:
                continue
            if provider_filter != "Alle Quellen" and entry.provider != provider_filter:
                continue
            matching_entries.append(entry)

        self.table.setRowCount(len(matching_entries))
        for row_idx, entry in enumerate(matching_entries):
            item_name = QTableWidgetItem(entry.name)
            item_kind = QTableWidgetItem(entry.kind)
            item_provider = QTableWidgetItem(entry.provider)

            item_count = QTableWidgetItem()
            item_count.setData(Qt.ItemDataRole.DisplayRole, entry.count)

            item_name.setData(Qt.ItemDataRole.UserRole, entry)

            self.table.setItem(row_idx, 0, item_name)
            self.table.setItem(row_idx, 1, item_kind)
            self.table.setItem(row_idx, 2, item_provider)
            self.table.setItem(row_idx, 3, item_count)

        self.table.setSortingEnabled(True)

    def on_table_selection_changed(self) -> None:
        """Update the detail panel when a row is selected."""
        selected_items = self.table.selectedItems()
        if not selected_items:
            self.selected_entry = None
            self.btn_export_skill.setEnabled(False)
            self.lbl_detail_title.setText("Kontext-Inspektion")
            self.lbl_detail_subtitle.setText("Wähle einen Eintrag in der Tabelle aus.")
            self.detail_text.clear()
            return

        row = selected_items[0].row()
        item_name = self.table.item(row, 0)
        entry: AuditEntry | None = item_name.data(Qt.ItemDataRole.UserRole) if item_name else None

        self.selected_entry = entry
        self.btn_export_skill.setEnabled(entry is not None)

        if not entry:
            return

        self.lbl_detail_title.setText(f"Details: {entry.name}")
        self.lbl_detail_subtitle.setText(
            f"Typ: {entry.kind} | Quelle: {entry.provider} | {entry.count} Aufrufe insgesamt"
        )

        lines: list[str] = [
            f"=== Fundstellen für '{entry.name}' ({len(entry.findings)} Vorkommnisse) ===\n"
        ]
        for idx, finding in enumerate(entry.findings[:50], start=1):
            line_str = f":L{finding.line_number}" if finding.line_number else ""
            lines.append(f"[{idx}] {finding.file_path.name}{line_str}")
            lines.append(f"    Pfad: {finding.file_path}")
            if finding.context:
                lines.append(f"    Kontext: {finding.context}")
            lines.append("")

        if len(entry.findings) > 50:
            lines.append(f"... und {len(entry.findings) - 50} weitere Fundstellen.")

        self.detail_text.setPlainText("\n".join(lines))

    def export_selected_as_skill(self) -> None:
        """Export the currently selected audit entry as a structured SKILL.md file."""
        if not self.selected_entry:
            return

        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", self.selected_entry.name.lower()).strip("-")
        default_dir = Path(".agents") / "skills" / slug if Path(".agents").exists() else Path.cwd()
        default_file = default_dir / "SKILL.md"

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Skill-Datei speichern",
            str(default_file),
            "Markdown-Dateien (*.md);;Alle Dateien (*.*)",
        )
        if save_path:
            target_path = Path(save_path)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            content = generate_skill_markdown(self.selected_entry)
            target_path.write_text(content, encoding="utf-8")

            self.status_label.setText(f"Skill gespeichert: {target_path}")
            QMessageBox.information(
                self,
                "Skill exportiert",
                f"Der Workflow für '{self.selected_entry.name}' wurde erfolgreich exportiert nach:\n\n{target_path}",
            )

    def load_settings(self) -> None:
        """Load persisted window geometry and state from QSettings."""
        settings = QSettings("TGBox", "py-agent-audit")
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(1000, 700)

    def closeEvent(self, event) -> None:
        """Persist window geometry and settings on close."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(5000)
        settings = QSettings("TGBox", "py-agent-audit")
        settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)


def launch_app() -> None:
    """Entry point for running the PySide6 application."""
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    app.setStyleSheet(DARK_STYLESHEET)

    window = MainWindow()
    window.show()
    app.exec()
