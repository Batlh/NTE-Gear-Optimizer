from pathlib import Path
import json,sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from check_encoding import errors,scan
from import_patch15 import parse,serialize


@pytest.mark.parametrize('raw,expected',[(b'\xff','INVALID_UTF8'),(b'\xef\xbb\xbfhello','BOM'),(b'a\r\nb','CRLF'),('\u00c3\u00a4'.encode('utf-8'),'MOJIBAKE'),('\u00c3\u00b6'.encode('utf-8'),'MOJIBAKE'),('\u00c3\u00bc'.encode('utf-8'),'MOJIBAKE'),('\u00c3\u0178'.encode('utf-8'),'MOJIBAKE'),('\u00e2\u20ac\u201c'.encode('utf-8'),'MOJIBAKE')])
def test_detects_encoding_failures(raw,expected):
    assert expected in errors(raw)


def test_import_real_unicode_roundtrip(tmp_path):
    value='ÄÖÜ äöü ß – √ ±'
    source=tmp_path/'unicode.tsv'
    with source.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write('Name\tValue\nUmlaut\t'+value+'\n')
    raw=source.read_bytes()
    assert errors(raw)==[]
    columns,rows=parse(raw)
    assert rows[0]['Value']==value
    encoded=serialize({'columns':columns,'rows':rows})
    assert json.loads(encoded.decode('utf-8'))['rows'][0]['Value']==value
    assert value.encode('utf-8') in encoded
    restored=('\t'.join(columns)+'\n'+'\t'.join(rows[0][k] for k in columns)+'\n').encode('utf-8')
    assert restored==raw


def test_branch_text_encoding():
    assert scan(ROOT)=={}
