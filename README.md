# py-agent-audit

Ein schlankes, responsives Desktop-Audit-Dashboard zur automatisierten Analyse von Log-Dateien, Transkripten und Chat-Verläufen lokaler und IDE-integrierter KI-Coding-Agenten. Findet wiederkehrende Workflows, CLI-Befehle und interne Tool-Aufrufe und generiert daraus mit einem Klick standardisierte Agent-Skills (`SKILL.md`) oder stellt direkt einen integrierten **TokenOptimizer FastMCP-Server** bereit, um Token-Verbrauch und manuelle Eingriffe zu minimieren.

## Unterstützte KI-Quellen (Auto-Discovery)

- **Antigravity / Gemini**: Scannt Artefakte (`.md`), Logs und Session-JSONs.
- **Claude Desktop**: Analysiert MCP-Tool-Aufrufe (`mcp*.log`), sowohl für den klassischen Installer (`%APPDATA%/Claude/logs`) als auch für die Microsoft-Store-Version (`%LOCALAPPDATA%/Packages/Claude_*/LocalCache/Roaming/Claude/logs`).
- **GitHub Copilot**: Durchsucht VS-Code Chat-Sessions (`%APPDATA%/Code/User/globalStorage/emptyWindowChatSessions/*.json`).
- **Ollama**: Wertet Server-Logs (`%LOCALAPPDATA%/Ollama/server.log`) nach Endpunkten und Modellen aus.
- **Claude Code**: Wertet die Session-Transkripte (`~/.claude/projects/**/*.jsonl`) aus: Bash-Befehle, eingebaute Tools und MCP-Tool-Aufrufe.
- **Claude-App (Chats & Aufgaben)**: Diese liegen in der Cloud. Unter claude.ai > Einstellungen > Datenschutz > *Daten exportieren* den Export anfordern und die ZIP-Datei per Button **„Claude-Export...“** laden. Ausgewertet werden alle Tool-Aufrufe im Export. In Team-/Enterprise-Organisationen muss ein Owner den Export für Mitglieder freischalten.
- **TokenOptimizer**: Erfasst gemeldete Agenten-Engpässe (`~/.mcp_bottlenecks.jsonl`).
- **Benutzerdefinierte Workspaces**: Eigene Projektverzeichnisse können per Klick hinzugefügt werden.

## TokenOptimizer MCP-Server (Polyglot)

Das Projekt enthält einen vollständigen FastMCP-Server (`src/server.py`), der Coding-Agenten (z. B. Claude Desktop) 5 hocheffiziente, token-sparende Routine-Werkzeuge bereitstellt. Der Server ist **polyglot** konzipiert und unterstützt neben Python auch **Rust, Node/TypeScript, .NET/C#** und weitere Umgebungen:

1. **`run_compact_checks(project_dir: str)`**: Erkennt automatisch das Projekt-Ökosystem (Rust: `cargo check`, Node/TypeScript: `npm test` / `npx tsc`, .NET: `dotnet build`, Python: `uv run ruff check` & `uv run pytest`) und liefert nur kompakte Fehlerzeilen ohne riesige Tracebacks.
2. **`read_code_signatures(file_path: str)`** (Alias: `read_python_signatures`): Extrahiert Signaturen von Klassen, Interfaces, Structs und Funktionen ohne Rumpf für Python (`.py`), Rust (`.rs`), TypeScript/JavaScript (`.ts`, `.tsx`, `.js`, `.jsx`) und C# (`.cs`) (80–90% Tokenersparnis).
3. **`get_compact_git_diff(project_dir: str, staged_only: bool)`**: Liefert Git-Status & Diff mit `--unified=0` unter automatischem Ausschluss von Lockfiles (`Cargo.lock`, `package-lock.json`, `uv.lock`), Binärdateien und Minified Bundles.
4. **`get_project_tree(project_dir: str, max_depth: int)`**: Erzeugt einen bereinigten Projektbaum inklusive Zeilenzahlen (LOC) pro Codedatei unter Ausschluss von Build- und Dependency-Ordnern (`target`, `node_modules`, `bin`, `obj`, `.venv` etc.).
5. **`log_bottleneck(task_description: str, steps_taken: int, reason: str)`**: Ermöglicht dem Agenten, übermäßige Schleifen oder Engpässe direkt nach `~/.mcp_bottlenecks.jsonl` zu melden.

### Architektur & Token-ROI: Warum dieser Server kein Kontextfenster verschwendet

Ein häufiges Bedenken bei MCP-Servern ist: *„Erhöht die permanente Registrierung von Tools im LLM-System-Prompt nicht das reguläre Kontextfenster so stark, dass die Einsparungen zunichte gemacht werden?“*

Die Antwort für `TokenOptimizer` lautet **Nein** – aus drei entscheidenden architektonischen Gründen:

1. **Server-Side Polymorphismus statt Tool-Sprawl:**  
   Es werden *keine* Dutzenden Einzeltasks (wie `read_rust_signatures`, `read_csharp_signatures`, `run_cargo_checks`, `run_npm_checks` etc.) im Tool-Katalog registriert. Stattdessen gibt es nur **ein einziges** generisches Tool `read_code_signatures(file_path)` und `run_compact_checks(project_dir)`. Die Erkennung von Projektstrukturen und Dateiendungen geschieht zu 100 % lokal auf dem Python-Server – das LLM sieht dafür **0 zusätzliche Schema-Tokens**.
2. **Minimaler Schema-Overhead (~500 Tokens):**  
   Die 5 Tools besitzen bewusst simple Parameter (`str`, `bool`, `int`) ohne verschachtelte JSON-Objekte. Der gesamte Tool-Katalog belegt zusammengerechnet nur ca. **450 bis 550 Tokens** im System-Prompt.
3. **Anthropic Prompt Caching:**  
   In Claude Desktop greift für System-Prompts und Tool-Definitionen automatisches Caching. Nach der ersten Anfrage kosten diese Definitions-Tokens praktisch keine Latenz und bis zu 90 % weniger Token-Budget.

#### Der ROI-Vergleich (Aufwand vs. Ersparnis)

| Entwicklungs-Aktion | Ohne TokenOptimizer (Standard-Tools) | Mit TokenOptimizer MCP | Netto-Ersparnis |
| :--- | :--- | :--- | :--- |
| **Datei untersuchen** (z. B. 600 Zeilen TypeScript/Rust) | Liest gesamte Datei: **~4.500 Tokens** (bleiben über den ganzen Chat im Verlauf). | `read_code_signatures`: Liefert nur Structs/Interfaces: **~200 Tokens**. | **+ 4.300 Tokens gespart** |
| **Git-Diff analysieren** (inkl. Lockfiles) | `git diff` bläst `package-lock.json` / `Cargo.lock` unkomprimiert hinein: **10.000–40.000 Tokens**. | `get_compact_git_diff`: Schließt Lockfiles & Assets automatisch aus: **~300 Tokens**. | **+ 10.000–35.000 Tokens gespart** |
| **Build- & Testfehler prüfen** | Komplette Tracebacks und Terminal-Dumps: **~3.000–8.000 Tokens**. | `run_compact_checks`: Filtert auf isolierte Fehlerzeilen: **~150 Tokens**. | **+ 4.000 Tokens gespart** |

> [!TIP]
> **Fazit:** Ein fixer, gecachter Schema-Overhead von ~500 Tokens amortisiert sich bereits beim **ersten einzigen Tool-Aufruf** um das 8- bis 70-Fache.

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
