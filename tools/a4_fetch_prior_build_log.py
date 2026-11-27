"""Use CI's existing read-only Actions token; never print or save its value."""

from collections import deque
import json
import os
from pathlib import Path
import subprocess
import re
from a4_run_android_build import safe_line

assert os.environ.get('GITHUB_ACTIONS') == 'true'
out = Path('build/a4_prior_build_diagnostic')
out.mkdir(parents=True, exist_ok=False)
job_id = int(os.environ.get('NTE_PRIOR_BUILD_JOB_ID', '140760246804'))
assert job_id > 0
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
tail = deque(maxlen=800)
context = deque(maxlen=200)
previous = deque(maxlen=3)
following = 0
root_pattern = re.compile(
    r'FAILURE:|What went wrong:|Could not (?:resolve|GET|HEAD|find)|Received status code|No space left|(?:^|\s)error:|Execution failed for task|BUILD FAILED',
    re.IGNORECASE,
)
for line in process.stdout:
    clean = safe_line(line)
    tail.append(clean)
    if root_pattern.search(clean):
        context.extend(previous)
        context.append(clean)
        following = 4
    elif following:
        context.append(clean)
        following -= 1
    previous.append(clean)
with (out / 'prior_build_failure_context.txt').open(
    'x', encoding='utf-8', newline='\n'
) as f:
    f.write(''.join(context))
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
            'failure_context_lines': len(context),
            'scope': 'Last800lines plus bounded error context from original GitHub log; credential-related lines omitted.',
        },
        f,
        indent=2,
    )
    f.write('\n')
print('Prior NTE build-log capture:', code, 'tail lines:', len(tail))
