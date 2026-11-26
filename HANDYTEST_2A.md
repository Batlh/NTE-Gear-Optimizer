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
4. Unter Teil X/Y in Skalierung und Boni jeweils ausdrücklich „kein Bonus (0)“
   drücken. Dann nur die unten genannten Felder ändern. Ein leeres Feld ist
   kein Nullwert. Die beiden Prozent-Skalierungsfelder bleiben ausdrücklich 0.

## Drei Vergleiche

| Fall | Eingaben | Erwartung | Vertragsquelle |
|---|---|---|---|
| 1 | Teil X: skalierender flacher Wert 10; Teil Y: 20 | Besser; Verhältnis 1,100000000; Gesamtänderung +10 | KP01_UNUSED_BAD_MASTER / unveränderter OPB-05-Faktorpfad, 100 → 110 |
| 2 | Zur Auswahl zurück. Krit „ja“. Aktuell Krit-Rate 50, Krit-Schaden 100. Teil X/Y: flacher Wert jeweils 10; Krit-Rate 0 → 10; Krit-Schaden 0 → 0. | Besser; Verhältnis 1,066666667 | KP04_CRIT_WEIGHT |
| 3 | Wieder Krit „nein“. Aktuell Gesamtwert 100. Teil X flacher Wert 100; Teil Y 0. Alle Bonusfelder ausdrücklich 0. | Schlechter; Verhältnis 0,000000000; kein Fehlerdialog | KP04_AFTER_ZERO |

Zusätzlich prüfen: Vor/Zurück behält Werte. Ein geleertes relevantes Bonusfeld
zeigt ein unbestimmtes Ergebnis und eine konkrete Hilfe; bekannte Teilwerte
und Änderungen bleiben sichtbar. Ein nicht relevantes Krit-Feld darf bei
Krit „nein“ nicht als Pflichtfeld erscheinen. Ark unter Lv80 zeigt einen
unbekannten Grundwert, keine geschätzte Kurve. Guide 1.4 ist für 1.5 ungeprüft.

Bitte Gerät/Android-Version, Lesbarkeit und die drei sichtbaren Ergebnisse
notieren. Dieser Handytest ist noch kein durch den Builder erbrachter Beleg.
