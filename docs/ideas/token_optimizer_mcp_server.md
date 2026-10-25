# Idee: Integrierter TokenOptimizer MCP-Server für py-agent-audit

## 1. Problem Statement

Wie können wir die Analyse-Erkenntnisse aus `py-agent-audit` direkt in messbare Token-Einsparungen ummünzen, indem wir Entwicklern einen integrierten FastMCP-Server an die Hand geben, der die 5 häufigsten Routine-Token-Fresser (Git-Diffs, Test-/Linter-Läufe, Dateilesen, Projektstruktur und Engpässe) löst und sich mit einem Klick in Claude Desktop einbinden lässt?

## 2. Empfohlene Richtung

Die beiden Skripte [`tmp/server.py`](file:///c:/Users/DaniBani/Documents/VisualStudioCodeProjects/py-agent-audit/tmp/server.py) und [`tmp/server-add-on.py`](file:///c:/Users/DaniBani/Documents/VisualStudioCodeProjects/py-agent-audit/tmp/server-add-on.py) werden als vollwertiges Modul `src/server.py` in das Projekt integriert.

### Kernkomponenten

1. **MCP Server (`src/server.py`)**:
   - `run_compact_checks(project_dir: str)`: Führt Ruff und Pytest aus und liefert nur kompakte Fehler (kein Header/Traceback-Spam).
   - `read_python_signatures(file_path: str)`: Extrahiert AST-Signaturen von Klassen und Funktionen ohne Funktionskörper (80–90% Tokenersparnis).
   - `get_compact_git_diff(project_dir: str, staged_only: bool)`: Status & Diff mit `unified=0`, schließt Lockfiles und Assets aus.
   - `get_project_tree(project_dir: str, max_depth: int)`: Bereinigter Projektbaum mit Zeilenzahlen (LOC) unter Ausschluss von Cache/Venv/Node-Modules.
   - `log_bottleneck(task_description: str, steps_taken: int, reason: str)`: Schreibt gemeldete Agenten-Engpässe nach `~/.mcp_bottlenecks.jsonl`.

2. **1-Klick Claude Desktop Registrierung (`src/mcp_installer.py`)**:
   - Erkennt `%APPDATA%/Claude/claude_desktop_config.json`.
   - Fügt den Server `py-agent-audit-optimizer` sauber via `uv run py-agent-audit-server` ein, ohne bestehende Server zu überschreiben.

3. **Audit-Integration**:
   - Das Audit-Dashboard scannt die generierte Datei `~/.mcp_bottlenecks.jsonl` automatisch und visualisiert gemeldete Agenten-Engpässe direkt in der Tabelle.

## 3. Zu validierende Annahmen

- [x] FastMCP (`mcp[cli]`) läuft zuverlässig über Standard-IO (stdio) unter Windows.
- [x] Python-AST-Signaturen sparen 80%+ Tokens beim Verstehen von Modulschnittstellen.
- [ ] Claude Desktop Config (`claude_desktop_config.json`) ist als Standard-JSON formatiert und kann atomar aktualisiert werden.

## 4. MVP-Umfang

- Bündelung aller 5 Tools in `src/server.py` mit Einstiegspunkt `py-agent-audit-server`.
- Sicheres Installations-Hilfsmodul für Claude Desktop.
- GUI-Aktion: Button „MCP-Server in Claude Desktop installieren“.
- Scanner-Erweiterung für `~/.mcp_bottlenecks.jsonl`.
- Vollständige Unit-Tests für alle 5 Tools und den Config-Installer.

## 5. Not Doing (und Begründung)

- Keine TCP/Websocket-Transporte im ersten Schritt (stdio reicht für Claude Desktop und Claude Code vollkommen aus).
- Keine automatische Modifikation des Quellcodes über MCP (reine Read-/Check-Tools zur Token-Reduktion).
