# Handytest Phase 2A

Revision 0 · 2026-11-26 · Status: Testanleitung · löst keine frühere Datei ab

Die APK ist eine automatisch mit einem Debug-Zertifikat signierte Test-App. Erst nach dem
Review auf dem eigenen Gerät testen. Es werden keine Eingaben gespeichert;
beim Schließen gehen sie verloren. Die App braucht keine Internetverbindung.

Die Zahlen unten sind absichtlich einfache Testzahlen, keine Charakterwerte.
Die erwarteten Ergebnisse stammen aus den abgenommenen Kernpfadfällen und
OPB-10. Nicht den eigenen Spielstand auf diese Beispielzahlen ändern.

## Gemeinsame Auswahl

1. Charakter Elyms wählen, Profil „Eigener Wertevergleich“. Ark darf unbekannt
   bleiben: Hier werden eingegebene Gesamtwerte verglichen, keine Ark-Kurve.
2. Leistungstyp Schaden, Skalierung ANG. Krit und Bruch jeweils „nein“,
   Zyklusreaktion „keine“. Weiter.
3. Unter aktuelle Werte den Gesamtwert 100 eintragen. In der Gruppe Boni
   ausdrücklich „kein Bonus (0)“ drücken. Weiter.
4. Unter aktuelles/neues Teil in Skalierung und Boni jeweils ausdrücklich „kein Bonus (0)“
   drücken. Dann nur die unten genannten Felder ändern. Ein leeres Feld ist
   kein Nullwert. Die beiden Prozent-Skalierungsfelder bleiben ausdrücklich 0.

## Drei Vergleiche

| Fall | Eingaben | Erwartung | Vertragsquelle |
|---|---|---|---|
| 1 | aktuelles Teil: skalierender flacher Wert 10; neues Teil: 20 | Besser; Verhältnis 1,100000000; Gesamtänderung +10 | KP01_UNUSED_BAD_MASTER / unveränderter OPB-05-Faktorpfad, 100 → 110 |
| 2 | Zur Auswahl zurück. Krit „ja“. Aktuell Krit-Rate 50, Krit-Schaden 100. aktuelles/neues Teil: flacher Wert jeweils 10; Krit-Rate 0 → 10; Krit-Schaden 0 → 0. | Besser; Verhältnis 1,066666667 | KP04_CRIT_WEIGHT |
| 3 | Wieder Krit „nein“. Aktuell Gesamtwert 100. aktuelles Teil flacher Wert 100; neues Teil 0. Alle Bonusfelder ausdrücklich 0. | Schlechter; Verhältnis 0,000000000; kein Fehlerdialog | KP04_AFTER_ZERO |

Zusätzlich prüfen: Vor/Zurück behält Werte. Ein geleertes relevantes Bonusfeld
zeigt ein unbestimmtes Ergebnis und eine konkrete Hilfe; bekannte Teilwerte
und Änderungen bleiben sichtbar. Ein nicht relevantes Krit-Feld darf bei
Krit „nein“ nicht als Pflichtfeld erscheinen. Ark unter Lv80 zeigt einen
unbekannten Grundwert, keine geschätzte Kurve. Guide 1.4 ist für 1.5 ungeprüft.

Bitte Gerät/Android-Version, Lesbarkeit und die drei sichtbaren Ergebnisse
notieren. Dieser Handytest ist noch kein durch den Builder erbrachter Beleg.


## Ergänzung 2A-1: Tausenderpunkt und Ergebnisansicht

Im Feld „Gesamt-ANG mit aktuellem Teil“ absichtlich `2.560` eingeben.
Direkt an diesem Feld muss stehen: „Bitte ohne Tausenderpunkt eingeben,
z. B. 2560 – oder Komma für Nachkommastellen“. Es darf nicht als 2,56
übernommen werden. Bekannte Teileänderungen bleiben im Ergebnis sichtbar.
Mit `2560` korrigieren. Dezimalzahlen mit Komma, z. B. `1,5`;
auch `1.5` wird mit einer konkreten Komma-Hilfe abgewiesen.

Das Ergebnis beginnt mit Urteil, Verhältnis und geänderten Werten. „Einzelwerte
anzeigen“ öffnet die Details; „Auch Nullen und unveränderte Werte anzeigen“
macht alle gespeicherten Eingaben sichtbar. Bei einem unbestimmten Ergebnis
bleiben relevante Nullwerte, fehlende Angaben und Eingabehilfen bereits in der
Zusammenfassung sichtbar. Ein-/Ausklappen darf das Urteil nicht ändern.
Die normale App zeigt keine Schrift-Testzeile.

## Ergänzung 2A-2

Die alte Debug-App einmal deinstallieren: Die neue Test-APK verwendet den
festen Projektschlüssel. Künftige Test-APKs sollen sich darüber installieren
lassen. Keine gespeicherten Nutzerdaten vorhanden; Eingaben gelten je Sitzung.

- Kurzer Tipp ins Feld: Tastatur bleibt offen, Feld sichtbar über der Tastatur.
- Komma erreichbar; „Fertig“ schließt die Tastatur; Wischen scrollt weiterhin.
- Jede Auswahlliste öffnen, nach unten wischen und letzten Eintrag wählen.
  Alle Einträge müssen erreichbar sein, die Liste bleibt im Bildschirm.
  „Abbrechen“ behält die bisherige Wahl. Charaktere sind nach Namen sortiert.
- Absichtlich in Schritt 2 „kein Bonus (0)“ weglassen: „Was fehlt“ steht oben.
  „Zu Schritt 2“ führt zurück, bisherige Eingaben bleiben erhalten.
- 2,560 zeigt „übernommen als 2,56“; 2 560 zeigt „übernommen als 2560“;
  1 5 erhält Feldhilfe und wird nicht zu 15.
- Kiwi statt altem Platzhalter als App-Symbol prüfen.
- Die drei bisherigen Vergleichsfälle erneut prüfen. Samsung-Tastatur und
  Gerätesystem notieren; Emulator-Ergebnis ersetzt diesen Gerätetest nicht.
