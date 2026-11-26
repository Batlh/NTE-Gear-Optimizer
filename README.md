# NTE Gear Optimizer

## English

In development. This is an unofficial fan tool, not affiliated with, operated
by or supported by Hotta Studio or Perfect World. Game names and trademarks
belong to their respective owners.

The MIT license (LICENSE) applies only to our own code. Game values and guide
recommendations have separate provenance: see data/SOURCES.md. They are not
relicensed under MIT.

Phase 1A provides a shared Python core, not a user interface. The v0.28 comparison
logic will be ported in Phase 1B. CPython CI tests 3.14.10; web-core tests Pyodide 314.0.8
(Python 3.14.2). Python 3.14 is the selected project line (PLATTFORM-14).

To run tests: `python -m pip install -r requirements-dev.txt`, then
`python -m pytest`. To check all tracked text files: `python tools/check_encoding.py`.

## Deutsch

In Entwicklung. Dies ist ein inoffizielles Fan-Werkzeug. Es ist nicht mit Hotta
Studio oder Perfect World verbunden und wird von ihnen weder betrieben noch
unterstützt. Spielnamen und Marken gehören ihren jeweiligen Rechteinhabern.

Die MIT-Lizenz (LICENSE) gilt nur für unseren eigenen Code. Spielwerte und
Guide-Empfehlungen haben eine eigene Herkunft: siehe data/SOURCES.md. Sie
werden nicht unter der MIT-Lizenz neu lizenziert.

Phase 1A liefert einen gemeinsamen Python-Kern, noch keine Oberfläche. Die
Vergleichslogik aus v0.28 wird in Phase 1B übertragen. Die CPython-CI prüft
3.14.10; web-core prüft Pyodide 314.0.8 (Python 3.14.2). Python 3.14 ist die
ausgewählte Projektlinie (PLATTFORM-14).

Tests ausführen: `python -m pip install -r requirements-dev.txt`, danach
`python -m pytest`. Alle versionierten Textdateien prüfen:
`python tools/check_encoding.py`.
