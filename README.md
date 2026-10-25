# py-agent-audit

Ein schlankes, responsives Desktop-Audit-Dashboard zur automatisierten Analyse von Log-Dateien, Transkripten und Chat-Verläufen lokaler und IDE-integrierter KI-Coding-Agenten. Findet wiederkehrende Workflows, CLI-Befehle und interne Tool-Aufrufe und generiert daraus mit einem Klick standardisierte Agent-Skills (`SKILL.md`), um Token-Verbrauch und manuelle Eingriffe zu reduzieren.

## Unterstützte KI-Quellen (Auto-Discovery)

- **Antigravity / Gemini**: Scannt Artefakte (`.md`), Logs und Session-JSONs.
- **Claude Desktop**: Analysiert MCP-Tool-Aufrufe (`mcp*.log`).
- **GitHub Copilot**: Durchsucht VS-Code Chat-Sessions (`%APPDATA%/Code/User/globalStorage/emptyWindowChatSessions/*.json`).
- **Ollama**: Wertet Server-Logs (`%LOCALAPPDATA%/Ollama/server.log`) nach Endpunkten und Modellen aus.
- **Claude Code**: Liest CLI-Skills und Session-Verläufe (`~/.claude`).
- **Benutzerdefinierte Workspaces**: Eigene Projektverzeichnisse können per Klick hinzugefügt werden.

## Features

- **Asynchroner Scan**: Kein UI-Einfrieren dank Hintergrund-Thread (`QThread`) mit Fortschrittsanzeige und Abbruchfunktion.
- **Echtzeit-Filterung**: Schnelle Suche nach Befehlen sowie Filterung nach Typ (`CLI Command`, `MCP Tool`, `Internal Tool`, `LLM Endpoint`) und Provider.
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
│   ├── scanner.py       # Scanner-Engine, Multi-Source Parsers & Skill-Generator
│   ├── build.py         # PyInstaller Build-Script
│   └── tools.py         # Lint & Format Hilfsskripte
├── tests/
│   ├── test_gui.py      # PySide6 Headless UI Tests
│   ├── test_main.py     # Entrypoint Tests
│   └── test_scanner.py  # Regex, Parser & Aggregation Tests
├── docs/
│   ├── ideas/           # Konzeption & Ideation-Dokumente
│   └── intent/          # Bestätigte Statements of Intent
├── pyproject.toml
└── README.md
```
