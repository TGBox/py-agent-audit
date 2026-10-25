# Statement of Intent: AI Agent Audit Dashboard

## 1. Übersicht & Zielsetzung (Outcome)

Ein schlankes, responsives Desktop-Dashboard auf Basis von **PySide6** zur Analyse von Agenten-Logs und -Artefakten. Die Anwendung scannt Log-Dateien und Transkripte von **Antigravity/Gemini** und **Claude Desktop** (sowie optional beliebige Projektordner/Workspaces), aggregiert wiederkehrende CLI-Befehle und interne Tool-Aufrufe und stellt diese mit Kontext-Drilldown dar.

## 2. Zielgruppe (User)

Entwickler, die mit Coding-Agenten arbeiten und durch Erkennung redundanter Workflows gezielt eigene Tools, Skripte oder Agent-Skills bauen wollen, um Token-Verbrauch und manuelle Wiederholungen zu reduzieren.

## 3. Hintergrund & Motivation (Why now)

Das Terminal-Skript (`tmp/example.py`) liefert nur statische Top-10-Listen ohne Kontext. Die GUI macht Pfade interaktiv wählbar, filtert Befehle in Echtzeit und zeigt per Klick genau an, in welchen Sessions und Code-Blöcken die Aktionen stattfanden.

## 4. Erfolgskriterien (Success)

- **Auto-Discovery & Custom Paths**: Automatische Erkennung von Claude Desktop (`%APPDATA%/Claude/logs`) und Antigravity (`~/.gemini/antigravity`, `AppData/Antigravity/logs`), plus Dateidialog für eigene Workspaces.
- **Asynchrones Scannen**: Nicht-blockierendes Einlesen im Hintergrund via `QThread` mit Fortschrittsbalken und Abbruchmöglichkeit.
- **Interaktive Tabelle**: Sortierbare Anzeige der häufigsten Befehle/Tools mit Aufrufzahlen und Filterfeld.
- **Kontext-Drilldown**: Auswahl eines Eintrags zeigt die exakten Fundstellen (Dateipfad, Zeile/Session, Code-Ausschnitt).
- **GUI-Standards**: Nahtloser Wechsel zwischen Fenster- und Vollbildmodus (F11), Speichern von Fenstergröße/Position via `QSettings`, modernes Dark Theme.

## 5. Rahmenbedingungen & Architektur (Constraints)

- **Technologie**: Python 3.12+, Paketmanagement via `uv`, GUI mit PySide6 (QtWidgets).
- **Schlanke Struktur**:
  - `src/scanner.py`: Datenmodell (`AuditEntry`, `Finding`), Log-Parser für Claude & Antigravity, Aggregation.
  - `src/gui.py`: PySide6 Hauptfenster, Tabellenansicht, Detail-Dock und Worker-Thread (`QThread`).
  - `src/main.py`: Einstiegspunkt und `QApplication`-Lifecycle.
- **Code-Standards**: Englischer Code (Variablen, Typen, Kommentare, Tests), deutsche Benutzeroberfläche.
- **Qualität**: Ruff für Linting/Formatting, Pytest für Parser-Tests in `tests/test_scanner.py`.

## 6. Nicht im Scope für MVP (Out of scope)

- Separate Provider für Copilot/Ollama/Cline (wird nach MVP-Validierung über dieselbe `scanner.py`-Schnittstelle ergänzt).
- Light-Theme-Umschaltung (wir starten mit einem sauberen Dark Theme).
- Automatische Codegenerierung neuer Tools.
- Binär- oder Datenbank-Parsing (reines Text-, JSON/JSONL- und Markdown-Parsing genügt).
