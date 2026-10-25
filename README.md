# py-agent-audit

A small python app to audit your coding agents log files for the most often used reoccurring tasks, in order to integrate tools for them to reduce your token usage in the future.

## Voraussetzungen

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Setup & Ausführung

```bash
uv sync

# GUI starten
uv run main
# oder:
uv run py-agent-audit

# Tests ausführen
uv run test

# Standalone-Exe mit PyInstaller bauen
uv run build
```

## Framework

Dieses Projekt verwendet **Tkinter**.

## Projektstruktur

```
py-agent-audit/
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── build.py
│   └── tools.py
├── tests/
│   └── test_main.py
├── pyproject.toml
└── README.md
```