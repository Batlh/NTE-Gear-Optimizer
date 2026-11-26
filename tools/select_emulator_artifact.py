"""Choose an owned-branch APK for a fast test; runtime source hashes MUST match."""

import json
import os
import urllib.request

assert os.environ.get('GITHUB_ACTIONS') == 'true'
assert os.environ.get('GITHUB_REPOSITORY') == 'Batlh/NTE-Gear-Optimizer'
request = urllib.request.Request(
    'https://api.github.com/repos/Batlh/NTE-Gear-Optimizer/actions/artifacts?name=android-emulator-only-apk&per_page=20',
    headers={
        'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
        'User-Agent': 'NTE-emulator-source-binding',
    },
)
with urllib.request.urlopen(request, timeout=30) as response:
    records = json.load(response)['artifacts']
choices = [
    a
    for a in records
    if not a['expired']
    and a['workflow_run']['head_branch'] == 'v029-phase2a'
    and a['workflow_run']['head_repository_id'] == a['workflow_run']['repository_id']
]
assert choices, 'No owned-branch emulator APK available'
artifact = max(choices, key=lambda a: a['created_at'])
with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8', newline='\n') as stream:
    stream.write('run_id=' + str(artifact['workflow_run']['id']) + '\n')
with open(os.environ['GITHUB_ENV'], 'a', encoding='utf-8', newline='\n') as stream:
    stream.write(
        'NTE_EXPECTED_APP_COMMIT=' + artifact['workflow_run']['head_sha'] + '\n'
    )
print(
    'Candidate emulator source',
    artifact['workflow_run']['head_sha'],
    'artifact',
    artifact['id'],
    '— test must verify every packaged app/core source hash before executing',
)
