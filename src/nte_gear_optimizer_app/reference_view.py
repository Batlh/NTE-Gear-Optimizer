"""Read-only historical facts; never fills an input or calls the engine."""

STAT_LABELS = {
    'FLAT_ATK': 'ANG',
    'FLAT_HP': 'LP',
    'STAT_ATK': 'ANG',
    'STAT_ATK_PCT': 'ANG',
    'STAT_DEF_PCT': 'VER',
    'STAT_HP_PCT': 'LP',
    'STAT_CRIT_RATE': 'Kritische Rate',
    'STAT_CRIT_DMG': 'Kritischer Schaden',
    'STAT_BREAK_INTENSITY': 'Bruchstärke',
    'STAT_CHARGE_EFFICIENCY': 'Ladeeffizienz',
    'STAT_ANIMA_DMG': 'Anima-Schaden',
    'STAT_COSMOS_DMG': 'Kosmos-Schaden',
}
NOTICE = 'Stand 1.4, für 1.5 ungeprüft. Nur zum Nachlesen; wird nicht in die Berechnung übernommen.'


def source_note(record):
    retrieved = record.get('SourceRetrievedAt', {}).get('Value')
    return (
        '\nQuelle: '
        + record['SourceRelativePath']
        + ' · Zeile '
        + str(record['SourceRow'])
        + '\nSHA-256: '
        + record['SourceSHA256']
        + '\nUrsprünglicher Abruf: '
        + (retrieved or 'nicht in der Quelle angegeben')
    )


def reference_sections(reference):
    names = {r['ArkID']: r['ArkName'] for r in reference['Arks']}
    sections = []
    arks = []
    for row in reference['ArkExactPoints'] + reference['ArkObservedPoints']:
        r = row['Original']
        name = names.get(r.get('CanonicalArkID'), 'Nicht zugeordnete Beobachtung')
        level = r.get('Level', r.get('ArkLevel', '?'))
        main = r.get('MainStatValue', '?')
        secondary = r.get('SecondaryValue', r.get('SecondaryStatValue', '?'))
        stat = STAT_LABELS.get(r.get('SecondaryStatID'), 'weiterer Wert')
        title = f'{name} · Lv {level}\nANG {main} · {stat} {secondary}'
        text = (
            NOTICE
            + '\n'
            + title
            + '\nAufstiegsstufe: '
            + r.get('ArkAscensionStage', 'nicht angegeben')
        )
        text += (
            '\nKeine Zwischenwerte und keine automatische Auswahl einer Beobachtung.'
            + source_note(row)
        )
        arks.append((row['RecordID'], title, text))
    sections.append(('ark', 'Ark-Levelwerte', arks))
    effects = {r['RecordID']: r for r in reference['SetEffects']}
    sets = []
    for row in reference['Sets']:
        text = NOTICE + '\n' + row['SetName']
        for key in row['EffectRecordIDs']:
            record = effects[key]
            r = record['Original']
            text += '\n\n' + r['Threshold'] + ' Teile: ' + r['RawSummary']
            text += (
                '\nQuellhinweis: ' + (r.get('Notes') or 'keiner') + source_note(record)
            )
        sets.append((row['SetID'], row['SetName'] + '\n1.4 ungeprüft', text))
    sections.append(('sets', 'Kassetten-Sets', sets))
    cartridges = []
    for row in reference['CartridgeLevels']:
        r = row['Original']
        label = STAT_LABELS.get(r['StatID'], 'weiterer Wert')
        title = f'Seltenheit {r["Rarity"]} · Lv {r["ItemLevel"]}\n{label}: {r["Value"]} Prozentpunkte'
        text = (
            NOTICE
            + '\n'
            + title
            + '\nBeobachtete Werte unterschiedlicher Exemplare; keine abgeleitete Aufwertungskurve.'
            + source_note(row)
        )
        cartridges.append((row['RecordID'], title, text))
    sections.append(('cartridges', 'Kassetten-Hauptwerte', cartridges))
    modules = []
    for row in reference['ModuleEndpoints']:
        r = row['Original']
        title = f'Typ {r["ModuleType"]} · Seltenheit {r["ModuleRarity"]} · Lv {r["EnhancementLevel"]}\nANG {r["FlatATK"]} · LP {r["FlatHP"]}'
        modules.append(
            (
                row['RecordID'],
                title,
                NOTICE
                + '\n'
                + title
                + '\nNur der belegte Endpunkt.'
                + source_note(row),
            )
        )
    for row in reference['ModuleLevelSeries']:
        r = row['Original']
        stat = STAT_LABELS.get(r['StatID'], 'weiterer Wert')
        title = f'Typ {r["ModuleType"]} · Seltenheit {r["Rarity"]}\n{stat} · Lv {r["LevelStart"]}–{r["LevelEnd"]}'
        values = '\n'.join(
            f'Lv {i}: {value}'
            for i, value in enumerate(
                r['ValueSequence_L0_to_L20'].split(','), int(r['LevelStart'])
            )
        )
        modules.append(
            (
                row['RecordID'],
                title,
                NOTICE + '\n' + title + '\n' + values + source_note(row),
            )
        )
    for row in reference['ModuleInGameSamples']:
        r = row['Original']
        title = f'Typ III · beobachtetes Exemplar · Lv {r["ItemLevel"]}\nANG {r["MainATK"]} · LP {r["MainHP"]}'
        modules.append(
            (
                row['RecordID'],
                title,
                NOTICE
                + '\n'
                + title
                + '\nSeltenheit nicht belegt. Einzelbeobachtung, keine allgemeine Kurve.'
                + source_note(row),
            )
        )
    sections.append(('modules', 'Module: belegte Werte', modules))
    mixing = []
    labels = {
        'Alternatives': 'Alternativen',
        'ConsumedCopy': 'Verbrauchte Kopie',
        'RetainedCopy': 'Behaltene Kopie',
        'ObservedEvidence': 'Beobachteter Vorgang',
        'PassiveValue': 'Effektwerte',
        'Maximum': 'Höchste Stufe',
    }
    for row in reference['ArkMixingContract']:
        r = row['Original']
        title = labels.get(r['Field'], 'Quellenhinweis') + '\n1.4 ungeprüft'
        text = (
            NOTICE
            + '\nAus dem alten Projektvertrag; keine vollständige Wertetabelle je Ark und Mischstufe.\n\nOriginalhinweis: '
            + r['Rule']
            + '\nBei fehlenden Daten: '
            + r['MissingTreatment']
            + source_note(row)
        )
        mixing.append((row['RecordID'], title, text))
    sections.append(('mixing', 'Mischstufen: Quellenhinweise', mixing))
    return sections
