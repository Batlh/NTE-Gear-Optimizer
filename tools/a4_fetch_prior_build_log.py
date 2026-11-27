"""Use CI's existing read-only Actions token; never print or save its value."""

from collections import deque
import json
import os
from pathlib import Path
import subprocess
from a4_run_android_build import safe_line

assert os.environ.get('GITHUB_ACTIONS') == 'true'
out = Path('build/a4_prior_build_diagnostic')
out.mkdir(parents=True, exist_ok=False)
job_id = 140727814112
process = subprocess.Popen(
    [
        'gh',
        'api',
        f'repos/Batlh/NTE-Gear-Optimizer/actions/jobs/{job_id}/logs',
        '--allow-escape-sequences',
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    encoding='utf-8',
    errors='replace',
)
tail = deque(maxlen=500)
for line in process.stdout:
    tail.append(safe_line(line))
stderr = process.stderr.read()
code = process.wait()
with (out / 'prior_build_tail.txt').open('x', encoding='utf-8', newline='\n') as f:
    f.write(''.join(tail))
with (out / 'prior_build_diagnostic.json').open(
    'x', encoding='utf-8', newline='\n'
) as f:
    json.dump(
        {
            'status': 'CAPTURED' if code == 0 and tail else 'UNVERIFIED_READ_FAILED',
            'job_id': job_id,
            'exit_code': code,
            'stderr': safe_line(stderr),
            'tail_lines': len(tail),
            'scope': 'Last500lines of original GitHub log; credential-related lines omitted.',
        },
        f,
        indent=2,
    )
    f.write('\n')
print('Prior NTE build-log capture:', code, 'tail lines:', len(tail))
