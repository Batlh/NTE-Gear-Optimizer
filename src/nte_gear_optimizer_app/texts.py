"""All application-authored German labels live here for future translation."""

TITLE = 'NTE Gear Optimizer'
SUBTITLE = 'Inoffizieller Wertevergleich · in Entwicklung'
STEPS = ('1  Auswahl', '2  Aktuelle Werte', '3  Teil X und Teil Y', '4  Ergebnis')
ZERO = 'kein Bonus (0)'
BACK = 'Zurück'
NEXT = 'Weiter'
FIELD_LABELS = {
    'ScaleDirect': 'Skalierender Gesamtwert (ANG / LP / VER)',
    'ScalingPercentPP': 'Skalierung in % auf dem Teil',
    'WhitePanelBase': 'Weiße Basis im Spiel (nur bei geändertem Prozentwert)',
    'UniversalPP': 'Universeller Bonus (%)',
    'ElementPP': 'Passender Elementbonus (%)',
    'SkillPP': 'Passender Fähigkeitsbonus (%)',
    'OtherPP': 'Weitere passende Boni (%)',
    'ReductionPP': 'Verringerung des Bonus (%)',
    'CritRatePP': 'Krit-Rate (%)',
    'CritDamagePP': 'Krit-Schaden (%)',
    'Break': 'Bruchstärke',
    'ExtraBreakBuff': 'Zusätzlicher Bruchfaktor (normiert)',
    'CycleIntensity': 'Zyklusstärke',
    'HealingPP': 'Heilungsbonus (%)',
    'ShieldPP': 'Schildbonus (%)',
}
TYPE_NAMES = {
    'UNKNOWN': 'unbekannt',
    'DAMAGE': 'Schaden',
    'HEAL': 'Heilung',
    'SHIELD': 'Schild',
    'BUFF': 'Verstärkung',
}
SCALE_NAMES = {
    'UNBEKANNT': 'unbekannt',
    'ANG': 'ANG',
    'LP': 'LP',
    'VER': 'VER',
    'BASIS_ANG': 'Basis-ANG (gleichbleibend)',
    'SONSTIGE': 'andere Skalierung',
}
BOOL_NAMES = {
    None: 'nicht belegt',
    'UNKNOWN': 'unbekannt',
    'TRUE': 'ja',
    'FALSE': 'nein',
}
CYCLE_NAMES = {
    None: 'nicht belegt',
    'UNKNOWN': 'unbekannt',
    'NONE': 'keine',
    'BLOSSOM': 'Blossom',
    'NOVA': 'Nova',
    'SCORCH': 'Scorch',
    'HEXED': 'Hexed',
    'STAIN': 'Stain',
}
VERDICTS = {'BETTER': 'Besser', 'WORSE': 'Schlechter', 'EQUAL': 'Gleich'}
INDETERMINATE = 'Unentscheidbar – benötigte Angaben oder eindeutige Zweige fehlen.'
MANUAL = 'Eigener Wertevergleich'
NO_CHOICE = 'nicht angegeben'
ALL_BRANCHES = 'alle belegten Zweige'
CURRENT_NOTE = 'Gesamtwerte im Spiel mit Teil X. Werte werden nicht aus ungeprüften Levelkurven geschätzt.'
SWAP_NOTE = 'Nur Werte der beiden Teile eintragen. Nach dem Tausch gilt: aktueller Gesamtwert + Y − X. Fehlend ist nicht 0.'
GUIDE_WARNING = 'Guide 1.4: für 1.5 nicht geprüft'
GUIDE_BASIS = 'Zielbasis nicht ausreichend belegt; Richtwert, keine Rechenvorgabe.'
ARK_WARNING = 'Ark-Werte unter Lv80 werden nicht geschätzt. Bereits enthaltene Boni nicht doppelt eingeben.'
NO_GUIDE = 'Keine belegten Guide-Ziele für diese Auswahl vorhanden.'
NOT_DPS = 'Statischer relativer Vergleich, keine Kampf- oder DPS-Simulation.'
ASSUMPTION = 'Eigene Profilangaben sind Annahmen für diesen Vergleich.'
NO_RESULT = 'Noch kein Ergebnis berechnet.'
KNOWN = 'Bekannte Werte und Änderungen'
CURRENT = 'Aktuell (mit X)'
PART_X = 'Teil X'
PART_Y = 'Teil Y'
DIFFERENCE = 'Änderung am Teil (Y − X)'
TOTAL_DIFFERENCE = 'Änderung am Gesamtwert'
GUIDE = 'Guide-Richtwerte und Herkunft'
HINTS = 'Hinweise'
LOGO = 'X / Y'
FONT_PROBE = 'Ä Ö Ü ä ö ü ß ± √'

UI = {
    'recalculate': 'Erneut berechnen',
    'character': 'Charakter',
    'ark': 'Ark',
    'ark_level': 'Ark-Level (darf unbekannt bleiben)',
    'profile': 'Profil',
    'legacy_profile': 'Guide 1.4 ungeprüft für 1.5',
    'new_profile': 'Guide 1.5',
    'branch': 'Leistungszweig',
    'all_branch_note': 'Jeder Zweig wird mit seinen eigenen belegten Angaben geprüft. Für eigene Angaben einen Zweig oder den eigenen Wertevergleich wählen.',
    'type': 'Leistungstyp',
    'scale': 'Skalierung',
    'crit': 'Krit möglich?',
    'break': 'Bruch relevant?',
    'cycle': 'Zyklusreaktion',
    'missing_profile': 'Für eine Rechnung Leistungstyp und Skalierung festlegen. Vorhandene Angaben bleiben beim Zurückgehen erhalten.',
    'parts_hint': 'Linkes Feld: Teil X. Rechtes Feld: Teil Y.',
}
FIELD_LABELS.update(
    {
        'ProfileType': 'Leistungstyp',
        'ScalingStat': 'Skalierung',
        'CritEligible': 'Krit-Anwendbarkeit',
        'BreakEligible': 'Bruch-Anwendbarkeit',
        'CycleType': 'Zyklusreaktion',
        'CharacterPanelBase': 'belegte Charakterbasis',
    }
)

SESSION = 'Eingaben bleiben nur in dieser geöffneten Sitzung.'
