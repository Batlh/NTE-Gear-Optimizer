import hashlib,json,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from import_patch15 import parse,serialize,MANIFEST_SHA
DATA=ROOT/'data/patch_1_5_r1'
P=json.loads((DATA/'payload.json').read_text(encoding='utf-8'))

def test_manifest():
    assert hashlib.sha256((DATA/'source/MANIFEST.tsv').read_bytes()).hexdigest().upper()==MANIFEST_SHA
    _,entries=parse((DATA/'source/MANIFEST.tsv').read_bytes())
    for entry in entries:
        if entry['Name'].endswith('.tsv'):
            data=(DATA/'source'/entry['Name']).read_bytes()
            assert len(data)==int(entry['Bytes'])
            assert hashlib.sha256(data).hexdigest().upper()==entry['SHA256'].upper()

@pytest.mark.parametrize('table',sorted(P['tables']))
def test_schema_lossless_nulls_provenance(table):
    columns,rows=parse((DATA/'source'/table).read_bytes())
    assert P['tables'][table]=={'columns':columns,'rows':rows}
    schema=json.loads((DATA/'schema.json').read_text())
    assert schema['tables'][table]==columns
    for row in rows:
        assert set(row)==set(columns)
        assert all(v is None or isinstance(v,str) for v in row.values())
        if 'SourceID' in columns:
            assert row['SourceID'] is not None
        if 'RetrievedAtUTC' in columns:
            assert row['RetrievedAtUTC'] is not None

def test_deterministic_serialization():
    assert serialize(P)==(DATA/'payload.json').read_bytes()

def test_decisions_no_invented_curve():
    assert P['decisions']['R15-04']['base_atk']=='570'
    assert P['decisions']['R15-04']['rejected_base_atk']=='154'
    assert P['decisions']['R15-04']['below_level80'] is None
    assert P['decisions']['R15-03']['formula']=='UNCHANGED_FOR_1_5'
    assert P['decisions']['R15-02']['legacy_1_4_guide_targets']=='NOT_VERIFIED_FOR_1_5'
    assert len(P['tables']['characters.tsv']['rows'])==26
    assert len(P['tables']['character_components.tsv']['rows'])==2236

def test_parser_rejects_corruption():
    with pytest.raises(ValueError):parse(b'A\tA\n1\t2\n')
    with pytest.raises(ValueError):parse(b'A\tB\n1\n')
    with pytest.raises(ValueError):parse(b'A\r\n1\r\n')
    assert parse(b'A\tB\n\t0\n')[1]==[{'A':None,'B':'0'}]
