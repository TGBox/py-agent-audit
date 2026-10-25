# py-agent-audit

Ein schlankes, responsives Desktop-Audit-Dashboard zur automatisierten Analyse von Log-Dateien, Transkripten und Chat-Verläufen lokaler und IDE-integrierter KI-Coding-Agenten. Findet wiederkehrende Workflows, CLI-Befehle und interne Tool-Aufrufe und generiert daraus mit einem Klick standardisierte Agent-Skills (`SKILL.md`) oder stellt direkt einen integrierten **TokenOptimizer FastMCP-Server** bereit, um Token-Verbrauch und manuelle Eingriffe zu minimieren.

## Unterstützte KI-Quellen (Auto-Discovery)

- **Antigravity / Gemini**: Scannt Artefakte (`.md`), Logs und Session-JSONs.
- **Claude Desktop**: Analysiert MCP-Tool-Aufrufe (`mcp*.log`).
- **GitHub Copilot**: Durchsucht VS-Code Chat-Sessions (`%APPDATA%/Code/User/globalStorage/emptyWindowChatSessions/*.json`).
- **Ollama**: Wertet Server-Logs (`%LOCALAPPDATA%/Ollama/server.log`) nach Endpunkten und Modellen aus.
- **Claude Code**: Liest CLI-Skills und Session-Verläufe (`~/.claude`).
- **TokenOptimizer**: Erfasst gemeldete Agenten-Engpässe (`~/.mcp_bottlenecks.jsonl`).
- **Benutzerdefinierte Workspaces**: Eigene Projektverzeichnisse können per Klick hinzugefügt werden.

## TokenOptimizer MCP-Server

Das Projekt enthält einen vollständigen FastMCP-Server (`src/server.py`), der Coding-Agenten (z. B. Claude Desktop) 5 hocheffiziente, token-sparende Routine-Werkzeuge bereitstellt:

1. **`run_compact_checks(project_dir: str)`**: Führt Ruff & Pytest aus und liefert nur kompakte Fehlerzeilen (keine riesigen Tracebacks).
2. **`read_python_signatures(file_path: str)`**: Extrahiert AST-Signaturen von Klassen und Funktionen ohne Funktionskörper (80–90% Tokenersparnis).
3. **`get_compact_git_diff(project_dir: str, staged_only: bool)`**: Liefert Git-Status & Diff mit `--unified=0` unter Ausschluss von Lockfiles und Assets.
4. **`get_project_tree(project_dir: str, max_depth: int)`**: Erzeugt einen bereinigten Projektbaum inklusive Zeilenzahlen (LOC) pro Codedatei.
5. **`log_bottleneck(task_description: str, steps_taken: int, reason: str)`**: Ermöglicht dem Agenten, übermäßige Schleifen oder Engpässe direkt nach `~/.mcp_bottlenecks.jsonl` zu melden.

### 1-Klick Installation in Claude Desktop

In der GUI steht ein Button **„In Claude Desktop installieren“** bereit, der den MCP-Server automatisch und sicher in `%APPDATA%/Claude/claude_desktop_config.json` registriert (inkl. automatischem Backup `.json.bak`).

Alternativ kann der Server direkt gestartet werden:

```bash
uv run py-agent-audit-server
```

## Features

- **Asynchroner Scan**: Kein UI-Einfrieren dank Hintergrund-Thread (`QThread`) mit Fortschrittsanzeige und Abbruchfunktion.
- **Echtzeit-Filterung**: Schnelle Suche nach Befehlen sowie Filterung nach Typ (`CLI Command`, `MCP Tool`, `Internal Tool`, `LLM Endpoint`, `Agent Bottleneck`) und Provider.
- **Kontext-Drilldown**: Auswahl eines Eintrags zeigt die exakten Fundstellen mit Dateipfaden, Zeilennummern und Code-Ausschnitten.
- **1-Klick Skill-Generator**: Exportiert jeden wiederkehrenden Befehl direkt als standardkonforme `SKILL.md`-Datei (z. B. nach `.agents/skills/<name>/SKILL.md`).
- **Modernes GUI**: Dark Theme, Fenster- und Vollbildmodus (`F11`), automatische Speicherung von Fenstergröße und Position (`QSettings`).

## Voraussetzungen

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Setup & Ausführung

```bash
# Abhängigkeiten synchronisieren
uv sync

# GUI starten
uv run main
# oder:
uv run py-agent-audit

# MCP-Server starten
uv run py-agent-audit-server

# Tests ausführen (pytest)
uv run test

# Code formatieren & prüfen (Ruff)
uv run format
uv run lint

# Standalone-Exe mit PyInstaller bauen
uv run build
```

## Projektstruktur

```text
py-agent-audit/
├── src/
│   ├── __init__.py
│   ├── main.py          # App-Einstiegspunkt
│   ├── gui.py           # PySide6 UI, Dark Theme & QThread Worker
│   ├── server.py        # TokenOptimizer FastMCP-Server
│   ├── mcp_installer.py # Claude Desktop Config-Installer
│   ├── scanner.py       # Scanner-Engine, Multi-Source Parsers & Skill-Generator
│   ├── build.py         # PyInstaller Build-Script
│   └── tools.py         # Lint & Format Hilfsskripte
├── tests/
│   ├── test_gui.py           # PySide6 Headless UI Tests
│   ├── test_main.py          # Entrypoint Tests
│   ├── test_mcp_installer.py # Claude Desktop Config Tests
│   ├── test_scanner.py       # Regex, Parser & Aggregation Tests
│   └── test_server.py        # TokenOptimizer MCP Tools Tests
├── docs/
│   ├── ideas/           # Konzeption & Ideation-Dokumente
│   └── intent/          # Bestätigte Statements of Intent
├── tasks/
│   ├── plan.md          # Detaillierter Architektur- & Umsetzungsplan
│   └── todo.md          # Task-Checkliste
├── pyproject.toml
└── README.md
```
