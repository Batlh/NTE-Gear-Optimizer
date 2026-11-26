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


def test_standalone_filesystem_fallback(tmp_path,monkeypatch):
    import check_encoding
    def forbidden(*args,**kwargs):raise AssertionError('Git must not be invoked without .git')
    monkeypatch.setattr(check_encoding.subprocess,'check_output',forbidden)
    with (tmp_path/'example.txt').open('x',encoding='utf-8',newline='\n') as stream:
        stream.write('äöü ß –\n')
    for folder in ['.tools','build','dist','.venv']:
        (tmp_path/folder).mkdir()
        (tmp_path/folder/'invalid.bin').write_bytes(b'\xff')
    assert check_encoding.file_list(tmp_path)==[Path('example.txt')]
    assert check_encoding.scan(tmp_path)=={}
    (tmp_path/'broken.txt').write_bytes(b'\xff')
    assert check_encoding.scan(tmp_path)=={'broken.txt':['INVALID_UTF8']}


def test_git_unavailable_falls_back(tmp_path,monkeypatch):
    import check_encoding
    (tmp_path/'.git').mkdir()
    with (tmp_path/'data.tsv').open('x',encoding='utf-8',newline='\n') as stream:
        stream.write('Name\nÄ\n')
    def unavailable(*args,**kwargs):raise FileNotFoundError('git missing')
    monkeypatch.setattr(check_encoding.subprocess,'check_output',unavailable)
    assert check_encoding.scan(tmp_path)=={}
