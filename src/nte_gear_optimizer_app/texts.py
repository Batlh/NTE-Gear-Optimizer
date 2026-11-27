"""All application-authored German labels live here for future translation."""

TITLE = 'NTE Gear Optimizer'
SUBTITLE = 'Inoffizieller Wertevergleich · in Entwicklung'
STEPS = (
    '1  Auswahl',
    '2  Aktuelle Werte',
    '3  Aktuelles und neues Teil',
    '4  Ergebnis',
)
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
CURRENT_NOTE = 'Gesamtwerte im Spiel mit aktuellem Teil. Werte werden nicht aus ungeprüften Levelkurven geschätzt.'
SWAP_NOTE = 'Nur Werte der beiden Teile eintragen. Nach dem Tausch gilt: aktueller Gesamtwert + neues Teil − aktuelles Teil. Fehlend ist nicht 0.'
GUIDE_WARNING = 'Guide 1.4: für 1.5 nicht geprüft'
GUIDE_BASIS = 'Zielbasis nicht ausreichend belegt; Richtwert, keine Rechenvorgabe.'
ARK_WARNING = 'Ark-Werte unter Lv80 werden nicht geschätzt. Bereits enthaltene Boni nicht doppelt eingeben.'
NO_GUIDE = 'Keine belegten Guide-Ziele für diese Auswahl vorhanden.'
NOT_DPS = 'Statischer relativer Vergleich, keine Kampf- oder DPS-Simulation.'
ASSUMPTION = 'Eigene Profilangaben sind Annahmen für diesen Vergleich.'
NO_RESULT = 'Noch kein Ergebnis berechnet.'
KNOWN = 'Bekannte Werte und Änderungen'
CURRENT = 'Aktuelle Werte (mit aktuellem Teil)'
PART_X = 'Aktuelles Teil'
PART_Y = 'Neues Teil'
DIFFERENCE = 'Änderung am Teil (neu − aktuell)'
TOTAL_DIFFERENCE = 'Änderung am Gesamtwert'
GUIDE = 'Guide-Richtwerte und Herkunft'
HINTS = 'Hinweise'
LOGO = 'Aktuelles Teil ↔ Neues Teil'
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
    'parts_hint': 'Linkes Feld: aktuelles Teil. Rechtes Feld: neues Teil.',
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

SESSION = (
    'Eingaben werden beim Neustart geleert. Das lokale Debugprotokoll bleibt erhalten.'
)

GROUP_NAMES = {
    'scale': 'Skalierung',
    'bonus': 'Boni',
    'crit': 'Krit',
    'break': 'Bruch',
    'cycle': 'Zyklus',
    'heal': 'Heilung',
    'shield': 'Schild',
}
AFTER_TOTALS = 'Gesamtwerte nach dem Tausch'
BRANCH_HINTS = {
    'FIXED_OFFSET_STATUS_UNKNOWN': 'Der feste Anteil dieses Zweigs ist unbekannt. Der Vergleich ist nur ein Näherungswert.',
    'FIXED_OFFSET_NEAR_THRESHOLD': 'Der feste Anteil kann das Urteil nahe der Entscheidungsgrenze ändern.',
    'AFFINE_OFFSET_NOT_MODELLED': 'Skalierung und Bonus ändern sich zugleich; der feste Anteil ist dafür nicht ausreichend modelliert.',
    'FIXED_OFFSET_THRESHOLD_DATA_UNAVAILABLE': 'Für die Prüfung des festen Anteils fehlt eine belegte Größe.',
}
MESSAGES = {
    'empty': 'Keine bekannten Werte in diesem Bereich.',
    'source': 'Quelle: ',
    'unknown': 'unbekannt',
    'unknown_date': 'Datum unbekannt',
    'ratio': 'Verhältnis: ',
    'range': 'Mögliche Verhältnisse: ',
    'to': ' bis ',
    'invalid': 'Ungültige Zahl',
    'ark80': ' · Lv80 · Grund-ANG ',
    'ark_authority': ' (freigegebener Ausgangswert)',
    'ark_level': ' · Level ',
    'ark_unknown': ' · Grundwert unbekannt',
    'ark_invalid': 'Ark-Level ungültig: ganze Zahl von 1 bis 80. Der Vergleich eingegebener Gesamtwerte bleibt möglich.',
    'source_condition': 'Bedingung aus der Quelle: ',
    'source_old': 'Quellprofil: für 1.5 nicht geprüft.',
    'branch': 'Zweig ',
    'current_suffix': ' aktuell',
    'after_suffix': ' nach Tausch',
}


def field_label(field, scale, parts=False, after=False):
    if field == 'ScaleDirect':
        return (
            ('Flache ' + SCALE_NAMES.get(scale, 'Skalierung') + ' auf dem Teil')
            if parts
            else (
                'Gesamt-'
                + SCALE_NAMES.get(scale, 'Skalierung')
                + (' mit neuem Teil' if after else ' mit aktuellem Teil')
            )
        )
    if field == 'ScalingPercentPP':
        return SCALE_NAMES.get(scale, 'Skalierung') + ' (%) auf dem Teil'
    return FIELD_LABELS.get(field, field)


MESSAGES['select_branch_scale'] = (
    'Einen Leistungszweig wählen: die Zweige benötigen unterschiedliche Gesamtwerte. Bekannte Teileänderungen bleiben sichtbar.'
)


STATUS_HINTS = {
    'INDETERMINATE_MISSING_DEPENDENCY': 'Für diesen Vergleich fehlen relevante Angaben oder die möglichen Fälle führen zu unterschiedlichen Ergebnissen.',
    'NICHT_ENTSCHEIDBAR': 'Die Leistungszweige oder die Prüfung des festen Anteils lassen kein gemeinsames Urteil zu.',
}
MESSAGES.update(
    {
        'status_unknown': 'Dieser Vergleich kann mit den vorliegenden Angaben nicht beurteilt werden.',
        'proxy': 'Näherungswert ohne festen Anteil (kein Urteil): ',
    }
)


THOUSANDS_HINT = (
    'Bitte ohne Tausenderpunkt eingeben, z. B. 2560 – oder Komma für Nachkommastellen'
)
DECIMAL_HINT = 'Bitte Komma für Nachkommastellen verwenden, z. B. 1,5.'
DETAILS_OPEN = 'Einzelwerte anzeigen'
DETAILS_CLOSE = 'Einzelwerte einklappen'
SHOW_ALL = 'Auch Nullen und unveränderte Werte anzeigen'
SHOW_CHANGED = 'Nur geänderte Einzelwerte anzeigen'
CHANGED = 'Geänderte Werte'
NO_CHANGES = 'Keine bezifferte Änderung vorhanden.'
EXPLANATION_VALUES = 'Werte zur Klärung des unbestimmten Ergebnisses'
UNPARSED = ' (nicht als Zahl übernommen)'
NO_SINGLE_RATIO = 'Kein einzelnes Verhältnis für diese gemeinsame Zweigentscheidung.'


def footer(test_mode=False, font_probe=False):
    return FONT_PROBE if test_mode and font_probe else SESSION
