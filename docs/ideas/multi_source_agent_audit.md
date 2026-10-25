# Idee: Multi-Source Agent Audit mit 1-Klick Skill-Export

## 1. Problem Statement

Wie können wir wiederkehrende Shell-Befehle und Werkzeuge aus heterogenen KI-Systemen (GitHub Copilot Chat in VS Code, Ollama Server-Logs, Claude Code CLI, Claude Desktop, Antigravity) mit minimalem Code-Aufwand erfassen, normalisieren und direkt in wiederverwendbare Agent-Skills überführen?

## 2. Empfohlene Richtung (Richtung B)

Erweiterung des bestehenden Scanners und der PySide6-GUI um zwei zentrale Kernfähigkeiten:

1. **Multi-Source Provider Registry**:
   - Ergänzung von **GitHub Copilot Chat** (`%APPDATA%/Code/User/globalStorage/emptyWindowChatSessions/*.json` und `workspaceStorage`), **Ollama** (`%LOCALAPPDATA%/Ollama/server.log`) und **Claude Code** (`~/.claude`).
   - Einheitliche Extraktion von Shell-Befehlen aus JSON- und Text-Payloads mittels Standardbibliothek (`json`, `re`, `pathlib`).
   - Dynamische Erkennung in der GUI mit an-/abwählbaren Checkboxen.
2. **1-Klick Skill- & Alias-Generator**:
   - Im Detail-Panel erhält jeder aggregierte Eintrag einen Button *„Als Skill exportieren“*.
   - Generiert automatisch eine standardisierte `SKILL.md`-Datei (z. B. für `.agents/skills/<name>/SKILL.md` oder ein lokales Projekt), die den Befehl, Kontext und Zweck dokumentiert, sodass KI-Agenten ihn in Zukunft als kompakten Skill aufrufen können, statt Tokens mit langen CLI-Ketten zu verbrennen.

## 3. Zu validierende Annahmen

- [x] **Dateipfade existieren auf dem Zielsystem**: Verifiziert auf Windows für Copilot, Ollama, Claude und Antigravity.
- [x] **Struktur der Copilot-Chats**: JSON-Dateien enthalten Markdown-Codeblöcke im `requests`- und `response`-Feld, die mit derselben Regex-Engine extrahiert werden können.
- [ ] **Ablageort für generierte Skills**: Auswahl zwischen lokalem Workspace (`.agents/skills/`) oder einem benutzerdefinierten Ordner via Dateidialog.

## 4. MVP-Umfang für Richtung B

- **Scanner-Erweiterung (`src/scanner.py`)**:
  - `scan_copilot_sessions(base_dir: Path) -> list[Finding]`
  - `scan_ollama_logs(log_file: Path) -> list[Finding]`
  - `generate_skill_template(entry: AuditEntry) -> str`
- **UI-Erweiterung (`src/gui.py`)**:
  - Provider-Checkboxen für Copilot und Ollama in der Quellen-Leiste.
  - Button *„Als Skill exportieren...“* im Detail-Panel.
  - Dialog zur Bestätigung/Speicherung des generierten Skills.
- **Tests (`tests/`)**:
  - Testfälle für Copilot-JSON-Parsing und Ollama-Log-Parsing.
  - Test für die Skill-Template-Generierung.

## 5. Not Doing (und Begründung)

- **Keine SQLite-Treiber**: `session-store.db` von Copilot wird nicht per Binär-Parser ausgelesen; die JSON-Chat-Sessions liefern bereits alle nötigen Daten mit 0 Abhängigkeiten.
- **Keine Live-Telemetrie / Socket-Überwachung**: Kein Hintergrund-Daemon, der permanent CPU-Zyklen frisst; reines On-Demand-Scannen.
- **Keine automatische Skill-Registrierung in fremden IDE-Configs**: Wir schreiben die saubere `SKILL.md`-Datei; der Nutzer entscheidet, wo sie abgelegt wird.

## 6. Offene Fragen

- Standard-Zielordner beim Skill-Export: Soll standardmäßig der aktive Workspace (`.agents/skills/`) vorgeschlagen werden?
