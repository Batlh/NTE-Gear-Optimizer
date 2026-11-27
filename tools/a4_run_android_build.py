"""CI build wrapper preserving a small redacted failure tail, not secret values."""

from collections import deque
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def safe_line(line):
    if re.search(
        r'(?i)(token|password|secret|authorization|credential|storepass|keypass)', line
    ):
        return '[credential-related build line omitted]\n'
    return line[:4000] + (' [line truncated]\n' if len(line) > 4000 else '')


def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true'
    tail = deque(maxlen=250)
    process = subprocess.Popen(
        ['buildozer', '-v', 'android', 'debug'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    for line in process.stdout:
        sys.stdout.write(line)
        tail.append(safe_line(line))
    code = process.wait()
    out = Path('build')
    out.mkdir(exist_ok=True)
    with (out / 'android_build_tail.txt').open(
        'x', encoding='utf-8', newline='\n'
    ) as f:
        f.write(''.join(tail))
    with (out / 'android_build_diagnostic.json').open(
        'x', encoding='utf-8', newline='\n'
    ) as f:
        json.dump(
            {
                'exit_code': code,
                'command': ['buildozer', '-v', 'android', 'debug'],
                'tail_lines': len(tail),
                'scope': 'Last250lines; credential-related lines omitted.',
            },
            f,
            indent=2,
        )
        f.write('\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
