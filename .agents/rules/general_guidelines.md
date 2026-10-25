# Allgemeine Projekt- & Code-Standards

1. **Sprachkonventionen**:
   - Quellcode-Kommentare, Docstrings, Klassen-, Funktions- und Variablennamen werden ausschließlich auf **Englisch** verfasst.
   - Benutzerseitige Texte (GUI, CLI-Ausgaben für Endanwender, Benachrichtigungen, Fehlermeldungen) werden auf **Deutsch** formuliert, sofern nicht anders spezifiziert.

2. **Code-Qualität & Design**:
   - Bevorzuge einfache, wartbare Lösungen gegenüber unnötig komplexen Abstraktionen (KISS / YAGNI).
   - Trenne Geschäftslogik strikt von Präsentations- und Eingabeschichten.
   - Verwende sprechende Namen und modulare Funktionen mit klar definierter Verantwortlichkeit (Single Responsibility Principle).

3. **Versionskontrolle & Git**:
   - Commits sollten atomar und mit aussagekräftigen Nachrichten formuliert werden.
   - Verwende SemVer (Semantic Versioning) für Versionierungen.
   - Keine temporären Artefakte, Build-Dateien oder sensiblen Zugangsdaten im Git-Repository einchecken.
