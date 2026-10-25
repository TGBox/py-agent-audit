# Desktop GUI & PySide6 Richtlinien

1. **Threading & Responsiveness**:
   - Führe zeitaufwändige Operationen niemals im UI-Thread aus.
   - Verwende `QThread` und Qt-Signale (`Signal`), um Fortschritte und Ergebnisse asynchron an die GUI zu melden.

2. **Fenstermodi**:
   - Die Anwendung muss sowohl im Fenstermodus als auch im Vollbildmodus (z. B. via F11) nahtlos bedienbar sein.
   - Fenstergröße und Position sollen beim Beenden persistent (z. B. via `QSettings`) gespeichert werden.

3. **Styling & Theme**:
   - Konsistente Stylesheets (QSS) verwenden.
   - Farben mit hohem Kontrast und guter Lesbarkeit einsetzen.
   - Dark und Light Themes implementieren und konsistent bei der Implementierung neuer Elemente anwenden.
