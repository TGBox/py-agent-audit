---
name: code-review
description: Führt ein gründliches Code-Review für das Projekt durch. Prüft Korrektheit, Typisierung, Architektur und Sicherheitsaspekte.
---

# Code-Review Skill

## Ablauf

1. **Diff analysieren**:
   - Geänderte und neue Dateien im Git-Working-Tree ermitteln (`git status`, `git diff`).
2. **Qualitätskriterien prüfen**:
   - Werden Typ-Annotationen durchgängig verwendet?
   - Sind Variablennamen und Kommentare auf Englisch?
   - Gibt es ungenutzten Code, TODO-Reste oder Debug-Ausgaben?
   - Entspricht der Code den Projekt-Regeln in `.agents/rules/`?
3. **Ergebnisbericht erstellen**:
   - Priorisierte Liste von Hinweisen (Fehler, Warnungen, Stilverbesserungen) mit konkreten Code-Referenzen.
