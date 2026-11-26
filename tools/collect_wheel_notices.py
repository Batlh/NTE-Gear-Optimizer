from importlib import metadata
from pathlib import Path
import shutil, json

output = Path('third_party_licenses/wheel_notices')
output.mkdir(parents=True, exist_ok=False)
record = []
for dist in metadata.distributions():
    name = dist.metadata.get('Name', 'unknown')
    for relative in dist.files or []:
        text = str(relative)
        if '.dist-info/' not in text or not any(
            word in relative.name.lower()
            for word in ('license', 'copying', 'notice', 'authors')
        ):
            continue
        source = Path(dist.locate_file(relative))
        if not source.is_file():
            continue
        target = output / name / relative.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target = target.with_name(str(len(record)) + '_' + target.name)
        shutil.copyfile(source, target)
        record.append(
            {
                'distribution': name,
                'version': dist.version,
                'source': text,
                'file': target.as_posix(),
            }
        )
with (output / 'inventory.json').open('x', encoding='utf-8', newline='\n') as target:
    json.dump(record, target, indent=2)
