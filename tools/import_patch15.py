"""Deterministic, lossless TSV import. No network access; source never modified."""

import argparse
import hashlib
import json
from pathlib import Path

MANIFEST_SHA = '2E11C047B2643A32D106A3361282BAB41FCCDD95C1947ECFA7E2BF048FC0CD2B'


def digest(data):
    return hashlib.sha256(data).hexdigest().upper()


def parse(data):
    text = data.decode('utf-8')
    if text.startswith('\ufeff') or '\r' in text:
        raise ValueError('TSV requires UTF-8 without BOM, LF')
    lines = text.splitlines()
    headers = lines[0].split('\t')
    if len(headers) != len(set(headers)):
        raise ValueError('duplicate columns')
    rows = []
    for line in lines[1:]:
        cells = line.split('\t')
        if len(cells) != len(headers):
            raise ValueError('TSV row width')
        rows.append(dict(zip(headers, (None if c == '' else c for c in cells))))
    return headers, rows


def convert(source):
    manifest = (source / 'MANIFEST.tsv').read_bytes()
    if digest(manifest) != MANIFEST_SHA:
        raise ValueError('manifest hash mismatch')
    _, entries = parse(manifest)
    tables, provenance = {}, []
    for entry in entries:
        name = entry['Name']
        if Path(name).name != name:
            raise ValueError('unsafe manifest path')
        raw = (source / name).read_bytes()
        if len(raw) != int(entry['Bytes']) or digest(raw) != entry['SHA256'].upper():
            raise ValueError('source hash mismatch: ' + name)
        provenance.append({'file': name, 'sha256': digest(raw), 'bytes': len(raw)})
        if name.endswith('.tsv'):
            columns, rows = parse(raw)
            tables[name] = {'columns': columns, 'rows': rows}
    # Preserve original observations/conflicts unchanged; decisions are a
    # distinct overlay so discarded 154 and unresolved precision are traceable.
    decisions = {
        'R15-03': {
            'formula': 'UNCHANGED_FOR_1_5',
            'authority': 'USER_2026-11-25_REVIEW_PATCH15_REV1',
        },
        'R15-04': {
            'level': '80',
            'base_atk': '570',
            'rejected_base_atk': '154',
            'arks': ['ARK_ECHOES_ON_HOLD', 'ARK_DOTTED_HORIZON'],
            'below_level80': None,
            'authority': 'USER_2026-11-25_REVIEW_PATCH15_REV1',
        },
        'R15-02': {'legacy_1_4_guide_targets': 'NOT_VERIFIED_FOR_1_5'},
    }
    return {
        'schema_version': '1',
        'patch': '1.5',
        'source_manifest_sha256': MANIFEST_SHA,
        'provenance': provenance,
        'tables': tables,
        'decisions': decisions,
    }


def serialize(payload):
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    ).encode('utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = serialize(convert(args.source))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as stream:
        stream.write(result)


if __name__ == '__main__':
    main()
