# NTE Gear Optimizer

## English

In development. This is an unofficial fan tool, not affiliated with, operated
by or supported by Hotta Studio or Perfect World. Game names and trademarks
belong to their respective owners.

The MIT license (LICENSE) applies only to our own code. Game values and guide
recommendations have separate provenance: see data/SOURCES.md. They are not
relicensed under MIT.

Phase 1B-1 adds the pure comparison core: branch-bound profiles, scoped validation,
panel channels, static factors, robust unknown/branch evaluation, guide reference
alignment and recommendations. Display-only Lv80 projection and the separate
heuristic item scorer are included. Phase 2A adds a German four-step Kivy app for Windows and Android debug tests.
There is no build/inventory import/export or saved-build feature. Test builds
keep a bounded, offline diagnostic journal in private app storage. The Debug
menu exports a report only after a privacy notice and your explicit action;
the app does not send it over the network. This is a review
candidate, not a release. Launch with `python main.py` after installing
`requirements-app.txt`; device test instructions are in HANDYTEST_2A.md.

CPython CI tests 3.14.10; web-core tests Pyodide 314.0.8 (Python 3.14.2), comparing
all semantic outputs. Python 3.14 is the selected project line (PLATTFORM-14).
See CORE_CONTRACTS.md for input conventions, provenance and supported boundaries.

To run tests: `python -m pip install -r requirements-dev.txt`, then
`python -m pytest`. To check all tracked text files: `python tools/check_encoding.py`.

## Deutsch

In Entwicklung. Dies ist ein inoffizielles Fan-Werkzeug. Es ist nicht mit Hotta
Studio oder Perfect World verbunden und wird von ihnen weder betrieben noch
unterstützt. Spielnamen und Marken gehören ihren jeweiligen Rechteinhabern.

Die MIT-Lizenz (LICENSE) gilt nur für unseren eigenen Code. Spielwerte und
Guide-Empfehlungen haben eine eigene Herkunft: siehe data/SOURCES.md. Sie
werden nicht unter der MIT-Lizenz neu lizenziert.

Phase 1B-1 ergänzt den reinen Vergleichskern: zweiggebundene Profile, lokale
Validierung, Panelkanäle, statische Faktoren, robuste Auswertung unbekannter
Faktoren und Zweige sowie Guide-Bezugsbasis und Empfehlungen. Die reine
Lv80-Anzeigeprojektion und die getrennte heuristische Teilebewertung sind enthalten.
Phase 2A ergänzt eine deutsche Kivy-App mit vier Schritten für Windows und
Android-Debugtests. Es gibt kein Speichern von Builds und kein Import-/Export-Modul
für Builds oder Inventar. Test-Builds führen ein begrenztes lokales Fehlerprotokoll
im App-Speicher. Das Debug-Menü gibt einen Bericht erst nach Datenschutzhinweis
und deinem ausdrücklichen Klick weiter; die App sendet nichts ins Netz.
Dieser Stand ist ein Review-Kandidat, kein Release. Nach Installation von
`requirements-app.txt` startet `python main.py` die App. Der Handytest steht
in HANDYTEST_2A.md.

Die CPython-CI prüft 3.14.10; web-core prüft Pyodide 314.0.8 (Python 3.14.2) und
vergleicht sämtliche semantischen Ausgaben. Python 3.14 ist die ausgewählte
Projektlinie (PLATTFORM-14). Eingaberegeln, Herkunft und Umfangsgrenzen stehen
in CORE_CONTRACTS.md.

Tests ausführen: `python -m pip install -r requirements-dev.txt`, danach
`python -m pytest`. Alle versionierten Textdateien prüfen:
`python tools/check_encoding.py`.
