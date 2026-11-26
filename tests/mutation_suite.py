"""Execute valid, deliberately mutated source against semantic oracles.

No production files are changed. Syntax/import errors do not count as kills.
The same probes run under CPython and Pyodide.
"""

import importlib, sys, types
from pathlib import Path
from decimal import Decimal
from nte_gear_optimizer.numbers import ValueUnavailable

P = {
    'ProfileType': 'DAMAGE',
    'ScalingStat': 'ANG',
    'CritEligible': 'FALSE',
    'BreakEligible': 'FALSE',
    'CycleType': 'NONE',
}


def values():
    return {
        **{
            s + k: '0'
            for s in ('Before', 'After')
            for k in ('UniversalPP', 'ElementPP', 'SkillPP', 'OtherPP', 'ReductionPP')
        },
        'BeforeScaleDirect': '100',
        'AfterScaleDirect': '110',
    }


def probe_profile(m):
    r = m.effective_profile(
        {'CritEligible': 'FALSE'},
        {'CritEligible': 'TRUE'},
        branch_id='B',
        override_branch_id='A',
    )
    assert r.values['CritEligible'] == 'FALSE'


def probe_layout(m):
    mask = {(r, c) for r in range(1, 6) for c in range(1, 6)} - {
        (1, 3),
        (4, 1),
        (4, 5),
        (5, 1),
        (5, 5),
    }
    assert m.layout(['x'], [{'cells': [(3, 1)]}], mask) is None


def probe_direct(m):
    o = dict(
        StatID='STAT_ATK',
        DirectInputValue='1234',
        BuildStateFingerprint='F',
        RulesetID='R',
        InActiveTeam=False,
        ObservationKind='PANEL_TOTAL',
        CaptureContext=None,
        Provenance='synthetic',
        ExternalDeclarations={k: 'NONE_DECLARED' for k in m.EXTERNAL_CLASSES},
    )
    assert (
        m.resolve_channel(
            'STAT_ATK',
            'DIRECT',
            observation=o,
            expected_fingerprint='F',
            ruleset_id='R',
        )['ActualValue']
        is None
    )


def probe_modes(m):
    assert (
        m.resolve_channel('STAT_CRIT_RATE', 'DIRECT').get('ErrorCode')
        == 'ERR_CHANNEL_MODE_NOT_SUPPORTED_V028'
    )


def probe_break(m):
    v = {
        **values(),
        'BeforeBreak': '0',
        'AfterBreak': '300',
        'BeforeExtraBreakBuff': '0',
        'AfterExtraBreakBuff': '0',
    }
    assert m.scenarios(v, {**P, 'BreakEligible': 'TRUE'})[0].ratio == Decimal('2.2')


def probe_float(m):
    assert m.number('0.100000000000000000000000000001') == Decimal(
        '0.100000000000000000000000000001'
    )


def probe_unknown(m):
    assert m.domain({'CritEligible': 'UNKNOWN'}, 'CritEligible', ('FALSE', 'TRUE')) == (
        'FALSE',
        'TRUE',
    )


def probe_epsilon(m):
    v = {
        **values(),
        'AfterScaleDirect': '150',
        'BeforeCritRatePP': '0',
        'AfterCritRatePP': '0.00000000001',
        'BeforeCritDamagePP': '100',
        'AfterCritDamagePP': '100',
    }
    assert m.evaluate_profile(v, {**P, 'CritEligible': 'UNKNOWN'})['RawRatio'] is None


def probe_branch(m):
    r = m.evaluate_branches(
        [m.Branch('a', P), m.Branch('b', P, {'AfterScaleDirect': '90'})], values()
    )
    assert r['BranchStatus'] == 'BRANCHES_DISAGREE'


def guide_row(**kwargs):
    return {
        'BeforeValue': '90',
        'AfterValue': '110',
        'TargetMinimum': '100',
        'ReferenceBasis': 'PANEL',
        'BeforeBasis': 'PANEL',
        'AfterBasis': 'PANEL',
        'ContextVerified': True,
        'CurrentLevel': 80,
        'TargetLevel': 80,
        'SubstatPriorityRank': 2,
        'Source': 'SYNTHETIC',
        'EvidenceID': 'test-only',
        **kwargs,
    }


def probe_rank(m):
    refs = [
        m.reference(
            guide_row(BeforeValue='150', AfterValue='150', SubstatPriorityRank=1)
        ),
        m.reference(guide_row()),
    ]
    assert m.rank_verdict(refs)['Verdict'] == 'BETTER'


def probe_gate(m):
    r = m.compare(values(), P, targets=[guide_row(ReferenceBasis=None)])
    assert r['OutputStatus'] == 'READY' and r['Verdict'] == 'BETTER'


def probe_projection(m):
    r = m.project(
        {
            'WhiteBasis': 'IN_GAME_WHITE_WITH_PROGRESS',
            'WhiteCurrent': '100',
            'White80': '200',
            'ActualTotal': '1000',
            'EquipmentPercent': None,
        }
    )
    assert r['ProjectedLv80Exact'] is None


def probe_score(m):
    weights = {**{str(i): '10' for i in range(4)}, **{str(i): '1' for i in range(4, 8)}}
    rolls = [
        {
            'StatID': str(i),
            'Value': '10',
            'Baseline': '10',
            'Minimum': '0',
            'Maximum': '10',
        }
        for i in range(4, 8)
    ]
    policy = {
        'Maximum score': '1',
        'Build relevance share': '0.6',
        'Roll quality share': '0.4',
        'Keep threshold': '0.85',
        'Review threshold': '0.65',
    }
    r = m.score_item(rolls, weights, policy, required_slots=4)
    assert r['Overall'] == '0.46' and r['Recommendation'] == 'Recycle'


# Format-independent semantic mutations.
MUTATIONS = [
    ('models.profile_state', 'M02_BRANCH_LEAK', probe_profile),
    ('validation.scoped', 'M03_AXES_TRANSPOSED', probe_layout),
    ('panels.resolution', 'M04_CONTEXT_BYPASS', probe_direct),
    ('panels.resolution', 'M04_MODE_BOUNDARY_REMOVED', probe_modes),
    ('numbers', 'M05_FLOAT_DECIMAL', probe_float),
    ('comparison.factors', 'M05_BREAK_DIVISOR', probe_break),
    ('comparison.factors', 'M06_UNKNOWN_FALSE', probe_unknown),
    ('comparison.robust_branches', 'M06_EPSILON', probe_epsilon),
    ('comparison.robust_branches', 'M06_FIRST_BRANCH', probe_branch),
    ('guide.reference', 'M07_FIRST_EXISTING_RANK', probe_rank),
    ('comparison.recommendation', 'M08_GLOBAL_GUIDE_GATE', probe_gate),
    ('projection.lv80', 'M09_NULL_PERCENT_ZERO', probe_projection),
    ('legacy.item_score', 'M10_SELECTED_STATS_DENOMINATOR', probe_score),
]


def transformed_source(source, identifier):
    """AST mutations survive mechanical formatting; every target is unique."""
    import ast

    tree = ast.parse(source)
    changes = 0

    def expression(text):
        return ast.parse(text, mode='eval').body

    class Mutator(ast.NodeTransformer):
        def visit_Assign(self, node):
            nonlocal changes
            self.generic_visit(node)
            name = (
                node.targets[0].id
                if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                else None
            )
            replacement = None
            if identifier == 'M02_BRANCH_LEAK' and name == 'bound':
                replacement = 'True'
            elif identifier == 'M03_AXES_TRANSPOSED' and name == 'cells':
                replacement = (
                    '[tuple(reversed(cell)) for p in placements for cell in p["cells"]]'
                )
            elif identifier == 'M05_FLOAT_DECIMAL' and name == 'n':
                replacement = 'Decimal(float(value))'
            elif (
                identifier == 'M06_FIRST_BRANCH'
                and name == 'verdicts'
                and isinstance(node.value, ast.SetComp)
            ):
                replacement = '{evaluated[0]["Verdict"]}'
            elif identifier == 'M07_FIRST_EXISTING_RANK' and name == 'rank':
                replacement = 'min(r["DecisionRank"] for r in references if r["DecisionRank"] is not None)'
            elif identifier == 'M10_SELECTED_STATS_DENOMINATOR' and name == 'best':
                replacement = 'selected'
            if replacement is not None:
                changes += 1
                node.value = expression(replacement)
            return node

        def visit_If(self, node):
            nonlocal changes
            self.generic_visit(node)
            test = ast.unparse(node.test)
            if identifier == 'M04_CONTEXT_BYPASS' and test == 'not valid':
                changes += 1
                node.test = ast.Constant(False)
            elif (
                identifier == 'M04_MODE_BOUNDARY_REMOVED'
                and test == 'stat_id in UNSUPPORTED_MODES'
            ):
                changes += 1
                node.test = ast.Constant(False)
            elif identifier == 'M06_UNKNOWN_FALSE' and test == "value == 'UNKNOWN'":
                changes += 1
                node.body = [ast.Return(expression('(closed[0],)'))]
            elif identifier == 'M06_EPSILON' and test == 'lo == hi':
                changes += 1
                node.test = expression("abs(lo-hi)<=Decimal('0.000000000001')")
            elif (
                identifier == 'M08_GLOBAL_GUIDE_GATE'
                and test == 'layout_issue is not None'
            ):
                changes += 1
                return ast.parse(
                    "if any(r['ReferenceUnavailableReason'] for r in refs): out.update(OutputStatus=MISSING,Verdict=None)"
                ).body + [node]
            elif (
                identifier == 'M09_NULL_PERCENT_ZERO'
                and test == "values.get('EquipmentPercent') is not None"
            ):
                changes += 1
                node.test = ast.Constant(True)
            return node

        def visit_BinOp(self, node):
            nonlocal changes
            self.generic_visit(node)
            if (
                identifier == 'M05_BREAK_DIVISOR'
                and isinstance(node.op, ast.Div)
                and isinstance(node.right, ast.Constant)
                and node.right.value == 300
            ):
                changes += 1
                node.right = ast.Constant(600)
            return node

        def visit_Call(self, node):
            nonlocal changes
            self.generic_visit(node)
            if (
                identifier == 'M09_NULL_PERCENT_ZERO'
                and isinstance(node.func, ast.Name)
                and node.func.id == 'number'
                and node.args
                and ast.unparse(node.args[0]) == "values['EquipmentPercent']"
            ):
                changes += 1
                node.args[0] = expression("values.get('EquipmentPercent') or '0'")
            return node

    tree = Mutator().visit(tree)
    assert changes == (2 if identifier == 'M09_NULL_PERCENT_ZERO' else 1), (
        identifier,
        changes,
    )
    return ast.fix_missing_locations(tree)


def run_mutations():
    report = []
    for suffix, identifier, probe in MUTATIONS:
        original = importlib.import_module('nte_gear_optimizer.' + suffix)
        probe(original)
        source = Path(original.__file__).read_text(encoding='utf-8')
        tree = transformed_source(source, identifier)
        name = '_nte_mutant_' + identifier
        module = types.ModuleType(name)
        module.__package__ = original.__package__
        module.Decimal = Decimal
        sys.modules[name] = module
        try:
            exec(compile(tree, original.__file__, 'exec'), module.__dict__)
            try:
                probe(module)
            except AssertionError:
                report.append({'ID': identifier, 'Result': 'KILLED'})
            else:
                raise AssertionError(identifier + ' survived')
        finally:
            del sys.modules[name]
    return report
