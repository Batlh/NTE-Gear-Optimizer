# Legacy references from the accepted v0.28 source

These are historical references, marked **Stand 1.4, für 1.5 ungeprüft**.
The current patch1.5 package is unchanged and takes precedence in display merges.
Original source patches, evidence status, conflicts and retrieval-date gaps remain explicit.
An import date is not a historical retrieval timestamp. No values were invented,
interpolated or extracted from cached workbook calculations.
The frozen workbook supplies existing Ark identities/types only. Level values
and effects retain their original TSV observations and source roles.
No legacy value is added automatically to the comparison engine or current stats.
Set effects and combat-dependent Ark effects remain reference text, not simulations.
The code’s MIT license does not relicense game data or original source material.

`reference.json` and the application asset are byte-identical. `MANIFEST.tsv`
binds this dataset; per-record provenance binds each original source row.
Set `EffectRecordIDs` refer to source records in `SetEffects`; they are not duplicate entities.
`schema.json` documents the versioned format; `legacy_reference.py` validates it.

## Deutsch

Dies sind historische Referenzen mit dem Hinweis **Stand 1.4, für 1.5 ungeprüft**.
Das Paket für 1.5 bleibt unverändert und hat bei Überschneidungen Vorrang.
Es gibt keine neuen Rechenregeln und keine automatische Übernahme der Zahlen.
Unklare oder fehlende Werte bleiben offen. Empfehlungen werden nicht zu Spielregeln.
Die Zuordnung Charakter → Ark-Typ fehlt: Alle Arks werden mit Typ gezeigt,
ohne Sperre oder Ausblendung. Eine spätere belegte Zuordnung kann den Filter aktivieren.
Die Namen „Far Side of the Moon“ in zwei Guide-Zeilen haben im angenommenen
Katalog noch keine zugeordnete Identität. Dafür wurde keine ID erfunden.
Die MIT-Lizenz gilt für eigenen Code; Spielwerte und Quellmaterial bleiben davon getrennt.

The six original Ark mixing-contract rows are retained separately as contract references,
not an Ark-by-tier numeric table. They do not authorize interpolation or engine defaults.
The two excluded Ark conflict observations keep their source dates from the frozen
workbook Sources table; original effect texts/values are unchanged.
