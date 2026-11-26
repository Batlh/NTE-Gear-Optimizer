"""Strict UTF-8 validation for both checkouts and standalone snapshots."""

from pathlib import Path
import re
import subprocess

MOJIBAKE = re.compile(
    r'\u00c3[\u0080-\u00bf\u0153\u0178\u017e\u017d\u0160\u0161]|\u00c2[\u0080-\u00bf]|\u00e2\u20ac|\ufffd'
)
EXCLUDED = {
    '.git',
    '.tools',
    '.venv',
    'build',
    'dist',
    '__pycache__',
    '.pytest_cache',
    'node_modules',
}


def errors(raw):
    problems = []
    if raw.startswith(b'\xef\xbb\xbf'):
        problems.append('BOM')
    if b'\r\n' in raw:
        problems.append('CRLF')
    try:
        text = raw.decode('utf-8', errors='strict')
    except UnicodeDecodeError:
        return problems + ['INVALID_UTF8']
    if MOJIBAKE.search(text):
        problems.append('MOJIBAKE')
    return problems


def file_list(root):
    root = Path(root)
    if (root / '.git').exists():
        try:
            return [
                Path(p)
                for p in subprocess.check_output(['git', 'ls-files', '-z'], cwd=root)
                .decode('utf-8')
                .split('\0')
                if p
            ]
        except OSError, subprocess.CalledProcessError:
            pass
    return sorted(
        p.relative_to(root)
        for p in root.rglob('*')
        if p.is_file()
        and not any(
            part in EXCLUDED or part.endswith('.egg-info')
            for part in p.relative_to(root).parts
        )
        and not p.name.endswith(('.pyc', '.pyo'))
        and '_REV_' not in p.name
        and '_INTERMEDIATE_' not in p.name
    )


def scan(root):
    root = Path(root)
    return {
        str(name): problem
        for name in file_list(root)
        if name.suffix.lower() not in {'.ttf', '.png', '.zip', '.apk'}
        and (problem := errors((root / name).read_bytes()))
    }


if __name__ == '__main__':
    result = scan(Path(__file__).resolve().parents[1])
    for path, problems in result.items():
        print(path, ','.join(problems))
    raise SystemExit(bool(result))
