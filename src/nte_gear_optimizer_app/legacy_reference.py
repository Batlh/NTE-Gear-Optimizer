"""Hash-bound historical reference data. Never a comparison-engine input."""

from copy import deepcopy
import hashlib
import json
from importlib.resources import files
import re

from .catalog import load_catalog

STATUS = 'V028_UNVERIFIED_FOR_15'
SOURCE_ARCHIVE = 'F85BFC95C13259DA2962259B454E5396FFDB165128A632967D32FC94BB60EBA3'
SOURCE_WORKBOOK = '1D07965C6EC3C9652AAD8750B84EECD01E9EA168A8DF37C1E5A3386FDA2799AE'
REFERENCE_GROUPS = (
    'ArkExactPoints',
    'ArkObservedPoints',
    'CartridgeLevels',
    'ModuleInGameSamples',
    'ModuleEndpoints',
    'ModuleLevelSeries',
    'CanonicalRegistry',
    'ArkEffectReference',
    'SetEffects',
)
ARK_TYPES = frozenset(('Gas', 'Liquid', 'Solid', 'Plasma', 'Synthesis'))


class ReferenceIntegrityError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ReferenceIntegrityError(message)


def unique(rows, key):
    require(isinstance(rows, list), 'Expected a record list')
    values = []
    for row in rows:
        require(isinstance(row, dict), 'Expected a record object')
        value = row.get(key)
        require(isinstance(value, str) and value != '', 'Missing identity')
        values.append(value)
    require(len(values) == len(set(values)), 'Duplicate identity')
    return set(values)


def validate_reference(doc):
    require(
        isinstance(doc, dict) and doc.get('SchemaVersion') == 1, 'Unsupported schema'
    )
    require(doc.get('DataStatus') == STATUS, 'Historical status missing')
    require(doc.get('SourceArchiveSHA256') == SOURCE_ARCHIVE, 'Wrong research source')
    require(doc.get('FrozenWorkbookSHA256') == SOURCE_WORKBOOK, 'Wrong workbook source')
    require(
        doc.get('Usage')
        == 'REFERENCE_ONLY_NO_ENGINE_MODIFICATION_NO_INTERPOLATION_NO_AUTOMATIC_WINNER',
        'Unsupported data use',
    )
    ark_ids = unique(doc.get('Arks'), 'ArkID')
    unique(doc.get('Sets'), 'SetID')
    require(
        isinstance(doc.get('CharacterArkTypes'), list), 'Missing type-mapping table'
    )
    require(isinstance(doc.get('ResearchSources'), list), 'Missing provenance registry')
    sources = {r['SourceRelativePath']: r for r in doc['ResearchSources']}
    require(len(sources) == len(doc['ResearchSources']), 'Duplicate source path')
    record_ids = set()
    for name in REFERENCE_GROUPS:
        rows = doc.get(name)
        ids = unique(rows, 'RecordID')
        require(not record_ids.intersection(ids), 'Duplicate source record')
        record_ids.update(ids)
        for row in rows:
            require(row.get('DataStatus') == STATUS, 'Unlabelled legacy record')
            relative = row.get('SourceRelativePath')
            source = sources.get(relative)
            require(source is not None, 'Unregistered source')
            require(
                row.get('SourceSHA256') == source['SHA256'], 'Source digest mismatch'
            )
            require(
                re.fullmatch('[0-9A-F]{64}', row['SourceSHA256']) is not None,
                'Invalid source digest',
            )
            number = row.get('SourceRow')
            require(type(number) is int and number >= 2, 'Invalid source row')
            require(
                row['RecordID'] == row['SourceSHA256'] + ':' + str(number),
                'Source identity mismatch',
            )
            require(isinstance(row.get('Original'), dict), 'Missing original record')
            require(
                isinstance(row.get('SourceRetrievedAt'), dict),
                'Missing retrieval status',
            )
            require(row.get('SourceRole') == source['Role'], 'Source role mismatch')
            require(
                row.get('OriginalArtifactStatus') == source['OriginalStatus'],
                'Artifact status mismatch',
            )
    canonical = {
        r['Original']['CanonicalID']
        for r in doc['CanonicalRegistry']
        if r['Original']['IDType'] == 'ARK'
    }
    require(ark_ids == canonical, 'Canonical Ark identity mismatch')
    for row in doc['Arks']:
        require(row.get('DataStatus') == STATUS, 'Unlabelled Ark')
        require(
            isinstance(row.get('ArkName'), str) and row['ArkName'] != '',
            'Missing display name',
        )
        require(row.get('ArkType') in ARK_TYPES, 'Unknown source Ark type')
        require(row.get('SourceSHA256') == SOURCE_WORKBOOK, 'Wrong identity source')
        require(
            row.get('SourceSheet') == 'Arks'
            and type(row.get('SourceRow')) is int
            and row['SourceRow'] >= 2,
            'Invalid identity source row',
        )
        require(
            isinstance(row.get('SourceRetrievedAt'), dict),
            'Missing identity retrieval status',
        )
    effect_ids = {r['RecordID'] for r in doc['SetEffects']}
    for row in doc['Sets']:
        require(row.get('DataStatus') == STATUS, 'Unlabelled set')
        require(
            isinstance(row.get('SetName'), str) and row['SetName'] != '',
            'Missing set name',
        )
        require(
            isinstance(row.get('EffectRecordIDs'), list), 'Missing effect references'
        )
        require(
            set(row['EffectRecordIDs']).issubset(effect_ids),
            'Unknown set-effect reference',
        )
    for row in doc['ArkExactPoints'] + doc['ArkObservedPoints']:
        original = row['Original']
        require(
            not original.get('CanonicalArkID') or original['CanonicalArkID'] in ark_ids,
            'Unknown observation identity',
        )
        for flag in (
            'AutomaticWinner',
            'Interpolation',
            'InterpolationAllowed',
            'UserInputDefault',
        ):
            value = original.get(flag, '')
            require(
                isinstance(value, str) and value.upper() in ('', 'FALSE', 'NO', '0'),
                'Automatic use of an observation is forbidden',
            )
    for row in doc['ModuleLevelSeries']:
        original = row['Original']
        values = original['ValueSequence_L0_to_L20'].split(',')
        require(
            len(values) == int(original['LevelEnd']) - int(original['LevelStart']) + 1,
            'Incomplete explicit level array',
        )
    counts = doc.get('Counts')
    require(isinstance(counts, dict), 'Missing counts')
    for key in (
        'Arks',
        'Sets',
        'ArkExactPoints',
        'ArkObservedPoints',
        'CartridgeLevels',
        'ModuleEndpoints',
        'ModuleLevelSeries',
        'ModuleInGameSamples',
    ):
        require(counts.get(key) == len(doc[key]), 'Record count mismatch')
    return doc


def load_reference(root=None):
    root = files('nte_gear_optimizer_app').joinpath('assets') if root is None else root
    payload = root.joinpath('legacy_v028_reference.json').read_bytes()
    manifest = json.loads(
        root.joinpath('legacy_v028_reference_manifest.json').read_text(encoding='utf-8')
    )
    require(
        isinstance(manifest, dict)
        and manifest.get('SchemaVersion') == 1
        and manifest.get('DataStatus') == STATUS,
        'Invalid reference manifest',
    )
    require(
        manifest.get('SourceArchiveSHA256') == SOURCE_ARCHIVE
        and manifest.get('FrozenWorkbookSHA256') == SOURCE_WORKBOOK,
        'Wrong manifest sources',
    )
    require(
        hashlib.sha256(payload).hexdigest().upper() == manifest.get('SHA256'),
        'Reference hash mismatch',
    )
    return validate_reference(json.loads(payload.decode('utf-8')))


def merge_reference_catalog(base, reference):
    validate_reference(reference)
    result = deepcopy(base)
    # Keep original1.5 records authoritative, including any overlapping IDs.
    current = {r['ArkID']: r for r in result['Arks']}
    for row in reference['Arks']:
        if row['ArkID'] not in current:
            current[row['ArkID']] = deepcopy(row)
    result['Arks'] = sorted(
        current.values(), key=lambda r: (r['ArkName'].casefold(), r['ArkID'])
    )
    result['LegacyReference'] = deepcopy(reference)
    result['LegacyReferenceWarning'] = None
    return result


def load_extended_catalog(root=None):
    base = load_catalog()
    try:
        return merge_reference_catalog(base, load_reference(root))
    except ReferenceIntegrityError, OSError, ValueError, TypeError, KeyError:
        # A broken optional reference must never block unrelated manual gear
        # comparison. It supplies no numbers or conditions to the engine.
        base['LegacyReference'] = None
        base['LegacyReferenceWarning'] = (
            'Die alten Referenzdaten sind nicht verfügbar. Der manuelle Teilevergleich bleibt möglich.'
        )
        return base


def filter_arks(arks, character_id, mappings):
    """Prepared for future sourced in-game mappings; no row means no filter."""
    matches = [
        r
        for r in mappings
        if isinstance(r, dict) and r.get('CharacterID') == character_id
    ]
    known = {
        r['ArkType']
        for r in matches
        if r.get('SourceKind') == 'USER_INGAME'
        and isinstance(r.get('SourceEvidence'), str)
        and r['SourceEvidence'].strip()
        and isinstance(r.get('ArkType'), str)
        and r['ArkType'] in ARK_TYPES
    }
    if len(known) != 1:
        return list(arks), 'NO_VERIFIED_CHARACTER_TYPE_SHOW_ALL'
    ark_type = next(iter(known))
    return [r for r in arks if r.get('ArkType') == ark_type], 'SOURCED_TYPE_FILTER'


def ark_display_name(row):
    suffix = ' · 1.4 ungeprüft' if row.get('DataStatus') == STATUS else ''
    return row['ArkName'] + '\nTyp: ' + row.get('ArkType', 'unbekannt') + suffix
