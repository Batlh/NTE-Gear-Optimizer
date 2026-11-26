"""Shared, runtime-independent semantic results for native/WebAssembly parity."""

import csv, json, sys
from pathlib import Path
from dataclasses import asdict
from decimal import localcontext, ROUND_DOWN
from core_case_runner import run_case, check_case
from mutation_suite import run_mutations
from nte_gear_optimizer.rules.opb10 import evaluate
from nte_gear_optimizer.validation.scoped import (
    validate_selected,
    character_level_valid,
    item_stats,
    ark_progress,
)
from nte_gear_optimizer.legacy.item_score import score_item

ROOT = Path(__file__).resolve().parents[1]


def run():
    cases = json.loads(
        (ROOT / 'tests/fixtures/core_cases.json').read_text(encoding='utf-8')
    )['Cases']
    results = {}
    for case in cases:
        r = run_case(case)
        check_case(case, r)
        results[case['CaseID']] = r
    opb = []
    for vector in csv.DictReader(
        (ROOT / 'tests/fixtures/opb10.tsv').open(encoding='utf-8'), delimiter='\t'
    ):
        r = evaluate(vector['Input'])
        assert (r.rounded, r.verdict) == (
            vector['ExpectedRounded'],
            vector['ExpectedVerdict'],
        )
        opb.append({'Input': vector['Input'], **asdict(r)})
    # Re-run under intentionally hostile ambient precision/rounding.
    with localcontext() as ctx:
        ctx.prec = 2
        ctx.rounding = ROUND_DOWN
        assert {c['CaseID']: run_case(c) for c in cases} == results
    report = validate_selected(
        [{'ID': 'a', 'Level': 80}, {'ID': 'bad', 'Level': 0}],
        'ID',
        'a',
        {'level': lambda r: character_level_valid(r['Level'])},
        ['level'],
    )
    assert report['Status'] == 'PASS'
    assert (
        validate_selected([{'ID': 'a'}], 'ID', 'a', {}, ['level'])['Status']
        == 'UNKNOWN'
    )
    policy = json.loads(
        (ROOT / 'tests/fixtures/scoring_policy.json').read_text(encoding='utf-8')
    )['Policy']
    rolls = [
        {
            'StatID': str(i),
            'Value': '10',
            'Baseline': '10',
            'Minimum': '0',
            'Maximum': '10',
        }
        for i in range(4)
    ]
    scoring = score_item(
        rolls, {str(i): '10' for i in range(4)}, policy, required_slots=4
    )
    assert scoring['Overall'] == '1'
    item_check = item_stats(
        [
            {
                'Role': 'MAIN',
                'Slot': 1,
                'StatID': 'STAT_ATK',
                'Unit': 'FLAT',
                'Value': '100',
            }
        ],
        kind='CARTRIDGE',
        level=5,
        stat_units={'STAT_ATK': 'FLAT'},
        permitted_main_ids={'STAT_ATK'},
        limits={('MAIN', 1, 'STAT_ATK'): ('0', '100')},
    )
    assert item_check == {'Status': 'UNKNOWN', 'Field': 'SubStats'}
    assert ark_progress(3, 40, {2: 40, 3: 50}) is None
    missing_caps = ark_progress(3, 40, {})
    assert (
        missing_caps.code is None
        and missing_caps.outcome == 'ARK_INSTANCE_NO_DEPENDENT_OUTPUT'
    )
    return {
        'core_cases': results,
        'opb10_vectors': opb,
        'mutations': run_mutations(),
        'validation': report,
        'item_score': scoring,
        'item_validation': item_check,
    }


if __name__ == '__main__':
    data = run()
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    with Path(sys.argv[1]).open('x', encoding='utf-8', newline='\n') as target:
        target.write(payload)
    print(
        json.dumps(
            {
                'core_cases': len(data['core_cases']),
                'opb10_vectors': len(data['opb10_vectors']),
                'mutations_killed': len(data['mutations']),
            }
        )
    )
