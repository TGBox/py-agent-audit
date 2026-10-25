# Python & uv Richtlinien

1. **Paket- und Umgebungsverwaltung**:
   - Verwende ausschließlich `uv` zur Verwaltung von Abhängigkeiten und virtuellen Umgebungen (`uv add`, `uv sync`, `uv run`).
   - Führe keine globalen `pip install`-Befehle aus.

2. **Typisierung & Syntax**:
   - Verwende moderne Python 3.12+ Typ-Annotationen (`list[str]`, `dict[str, Any]`, `X | None`).
   - Verwende `pathlib.Path` anstelle von veralteten `os.path`-Aufrufen.

3. **Code-Stil & Formatting**:
   - Alle Python-Dateien müssen den Ruff-Linter- und Formatierungsregeln entsprechen.
   - Vermeide Wildcard-Imports (`from module import *`).

4. **Testing**:
   - Tests werden mit `pytest` implementiert und via `uv run pytest` ausgeführt.
   - Testdateien beginnen mit `test_` und liegen im Verzeichnis `tests/`.
