"""Only bundled, hash-bound reference data. No user-file import interface."""

import json
from importlib.resources import files


def load_catalog():
    return json.loads(
        files('nte_gear_optimizer_app')
        .joinpath('assets/catalog.json')
        .read_text(encoding='utf-8')
    )


def branch_profile(row):
    return {**row, 'CycleType': row.get('CycleReactionType')}
