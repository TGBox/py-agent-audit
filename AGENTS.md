# Agent Workspace Configuration

Dieses Projekt ('py-agent-audit') enthält projektspezifische Richtlinien und Skills für Coding-Agenten im Verzeichnis `.agents/`.

## Aktive Regeln (`.agents/rules/`)

- **Allgemeine Architektur & Code-Standards**: Grundregeln: Saubere Modularisierung, lesbarer Code, englische Variablennamen/Kommentare, deutsche Nutzeroberflächentexte.
- **Python & uv Best Practices**: Moderne Python-Standards: Paketmanagement mit uv, Typ-Annotationen, Ruff Linter/Formatter und Pytest.
- **Desktop GUI & PySide6 Richtlinien**: Qt/PySide6 Konventionen: Trennung von Logik und UI, QThread/Worker für Hintergrundaufgaben, Fenster- und Vollbildmodus.

## Aktive Skills (`.agents/skills/`)

- **Code-Review Skill**: Strukturierte Überprüfung von Code-Änderungen hinsichtlich Korrektheit, Lesbarkeit, Sicherheit und Performance.
- **Test-Runner & Diagnose Skill**: Automatisiertes Ausführen und Analysieren von Tests mit den passenden Werkzeugen des Projekts (pytest, cargo test, vitest, unity).

## Richtlinien für KI-Agenten

1. Lies vor größeren Änderungen die anwendbaren Regeln in `.agents/rules/`.
2. Verwende die Skills in `.agents/skills/` für automatisierte Workflows wie Reviews und Tests.
3. Behalte die Projektstruktur sauber und folge den etablierten Konventionen.
