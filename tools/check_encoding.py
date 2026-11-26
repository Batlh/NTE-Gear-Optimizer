"""Reject malformed UTF-8, BOM, CRLF and accidental Windows-codepage recoding."""
from pathlib import Path
import re
import subprocess

# Escaped patterns so the checker itself does not contain corrupt text.
MOJIBAKE = re.compile(r"\u00c3[\u0080-\u00bf\u0153\u0178\u017e\u017d\u0160\u0161]|\u00c2[\u0080-\u00bf]|\u00e2\u20ac|\ufffd")


def errors(raw):
    problems=[]
    if raw.startswith(b'\xef\xbb\xbf'):problems.append('BOM')
    if b'\r\n' in raw:problems.append('CRLF')
    try:text=raw.decode('utf-8',errors='strict')
    except UnicodeDecodeError:return problems+['INVALID_UTF8']
    if MOJIBAKE.search(text):problems.append('MOJIBAKE')
    return problems


def scan(root):
    files=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode('utf-8').split('\0')
    findings={}
    for name in filter(None,files):
        raw=(root/name).read_bytes()
        problem=errors(raw)
        if problem:findings[name]=problem
    return findings


if __name__=='__main__':
    result=scan(Path(__file__).resolve().parents[1])
    for path,problems in result.items():print(path,','.join(problems))
    raise SystemExit(bool(result))
