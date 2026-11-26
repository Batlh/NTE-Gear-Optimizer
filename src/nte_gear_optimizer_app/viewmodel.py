"""Kivy-free presentation state; calculations are delegated to the pure core."""

from decimal import Decimal
from nte_gear_optimizer.models.profile_state import effective_profile
from nte_gear_optimizer.numbers import number, text, ValueUnavailable
from nte_gear_optimizer.comparison.swap import compile_swap
from nte_gear_optimizer.comparison.recommendation import compare
from nte_gear_optimizer.comparison.robust_branches import Branch
from .catalog import load_catalog, branch_profile
from . import texts as T

MANUAL_RELEASE = {
    'ProfileType': 'UNKNOWN',
    'ScalingStat': 'UNBEKANNT',
    'CritEligible': 'UNKNOWN',
    'BreakEligible': 'UNKNOWN',
    'CycleType': 'UNKNOWN',
}


def normalize(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueUnavailable('Eingabe', True)
    value = ''.join(value.split()).replace(',', '.')
    if not value:
        return None
    result = number(value)
    return '0' if result == 0 else text(result)


class ComparisonViewModel:
    def __init__(self, catalog=None):
        self.catalog = load_catalog() if catalog is None else catalog
        self.step = 0
        self.character_id = None
        self.ark_id = None
        self.ark_level = ''
        self.profile_id = None
        self.branch_id = None
        self.overrides = {}
        self.current = {}
        self.item_x = {}
        self.item_y = {}
        self.white_panel_base = ''
        self.last_result = None

    def next(self):
        self.step = min(3, self.step + 1)

    def back(self):
        self.step = max(0, self.step - 1)

    def choose_character(self, identifier):
        if identifier is not None and not any(
            r['CharacterID'] == identifier for r in self.catalog['Characters']
        ):
            raise ValueError('Charakter ist nicht im gebündelten Katalog')
        if identifier != self.character_id:
            self.current.clear()
            self.profile_id = None
            self.branch_id = None
            self.overrides.clear()
        self.character_id = identifier
        self.last_result = None

    def choose_ark(self, identifier):
        if identifier is not None and not any(
            r['ArkID'] == identifier for r in self.catalog['Arks']
        ):
            raise ValueError('Ark ist nicht im gebündelten Katalog')
        self.ark_id = identifier
        self.last_result = None

    def profiles(self):
        return [
            r for r in self.catalog['Profiles'] if r['CharacterID'] == self.character_id
        ]

    def branches(self):
        return [
            r
            for r in self.catalog['Branches']
            if r['BuildProfileID'] == self.profile_id
        ]

    def choose_profile(self, identifier):
        if identifier is not None and not any(
            r['BuildProfileID'] == identifier for r in self.profiles()
        ):
            raise ValueError('Profil passt nicht zum Charakter')
        self.profile_id = identifier
        self.branch_id = None
        self.overrides.clear()
        self._clear_scaling()

    def choose_branch(self, identifier):
        if identifier is not None and not any(
            r['ComparisonBranchID'] == identifier for r in self.branches()
        ):
            raise ValueError('Zweig passt nicht zum Profil')
        self.branch_id = identifier
        self.overrides.clear()
        self._clear_scaling()

    def _clear_scaling(self):
        for group in (self.current, self.item_x, self.item_y):
            group.pop('ScaleDirect', None)
            group.pop('ScalingPercentPP', None)
        self.white_panel_base = ''
        self.last_result = None

    def set_override(self, field, value):
        old = self.profile().get(field)
        self.overrides[field] = value
        if field == 'ScalingStat' and old != self.profile().get(field):
            self._clear_scaling()
        self.last_result = None

    def release(self):
        row = next(
            (r for r in self.branches() if r['ComparisonBranchID'] == self.branch_id),
            None,
        )
        if row:
            return branch_profile(row)
        return {
            **MANUAL_RELEASE,
            **({'BuildProfileID': self.profile_id} if self.profile_id else {}),
        }

    def profile(self):
        return dict(
            effective_profile(
                self.release(),
                self.overrides,
                branch_id=self.branch_id,
                override_branch_id=self.branch_id,
            ).values
        )

    @staticmethod
    def fields_for(profile):
        result = (
            ['ScaleDirect']
            if profile.get('ScalingStat') in ('ANG', 'LP', 'VER')
            else []
        )
        kind = profile.get('ProfileType')
        if kind == 'DAMAGE':
            result += ['UniversalPP', 'ElementPP', 'SkillPP', 'OtherPP', 'ReductionPP']
            if profile.get('CritEligible') != 'FALSE':
                result += ['CritRatePP', 'CritDamagePP']
            if profile.get('BreakEligible') != 'FALSE':
                result += ['Break', 'ExtraBreakBuff']
            if profile.get('CycleType') != 'NONE':
                result += ['CycleIntensity']
        elif kind == 'HEAL':
            result += ['HealingPP']
        elif kind == 'SHIELD':
            result += ['ShieldPP']
        return result

    def fields(self):
        if self.branches() and self.branch_id is None:
            return list(
                dict.fromkeys(
                    f
                    for b in self.branches()
                    for f in self.fields_for(branch_profile(b))
                )
            )
        return self.fields_for(self.profile())

    def groups(self, parts=False):
        active = self.fields()
        result = {}
        for name, fields in [
            ('Skalierung', ['ScaleDirect']),
            ('Boni', ['UniversalPP', 'ElementPP', 'SkillPP', 'OtherPP', 'ReductionPP']),
            ('Krit', ['CritRatePP', 'CritDamagePP']),
            ('Bruch', ['Break', 'ExtraBreakBuff']),
            ('Zyklus', ['CycleIntensity']),
            ('Heilung', ['HealingPP']),
            ('Schild', ['ShieldPP']),
        ]:
            subset = [f for f in fields if f in active]
            if subset:
                if parts and 'ScaleDirect' in subset:
                    subset.append('ScalingPercentPP')
                result[name] = subset
        return result

    def set_value(self, group, field, value):
        target = {'current': self.current, 'x': self.item_x, 'y': self.item_y}[group]
        target[field] = value
        self.last_result = None

    def zero_group(self, name, parts=False):
        fields = self.groups(parts=parts)[name]
        targets = (self.item_x, self.item_y) if parts else (self.current,)
        for group in targets:
            for field in fields:
                group[field] = '0'
        self.last_result = None

    def ark_summary(self):
        row = next((r for r in self.catalog['Arks'] if r['ArkID'] == self.ark_id), None)
        if row is None:
            return T.NO_CHOICE
        if (
            self.ark_level.strip() == '80'
            and row['ArkID'] in self.catalog['Decisions']['R15-04']['arks']
        ):
            return (
                row['ArkName']
                + ' · Lv80 · Grund-ANG '
                + self.catalog['Decisions']['R15-04']['base_atk']
                + ' (Nutzerentscheidung R15-04)'
            )
        return (
            row['ArkName']
            + ' · Level '
            + (self.ark_level.strip() or T.NO_CHOICE)
            + ' · Grundwert unbekannt'
        )

    def calculate(self):
        fields = self.fields()
        errors = {}

        def parsed(group, prefix, active):
            result = {}
            for field in active:
                try:
                    result[field] = normalize(group.get(field))
                except ValueUnavailable:
                    result[field] = None
                    errors[prefix + ' ' + T.FIELD_LABELS.get(field, field)] = (
                        'Ungültige Zahl'
                    )
            return result

        part_fields = fields + (['ScalingPercentPP'] if 'ScaleDirect' in fields else [])
        current = parsed(self.current, T.CURRENT, fields)
        x = parsed(self.item_x, T.PART_X, part_fields)
        y = parsed(self.item_y, T.PART_Y, part_fields)
        try:
            white = normalize(self.white_panel_base)
        except ValueUnavailable:
            white = None
            errors[T.FIELD_LABELS['WhitePanelBase']] = 'Ungültige Zahl'
        swap = compile_swap(current, x, y, fields, white_panel_base=white)

        # Retain valid known inputs even when the selected performance type
        # no longer consumes them. Invalid irrelevant input is not a gate.
        def known(group):
            result = {}
            for key, value in group.items():
                try:
                    result[key] = normalize(value)
                except ValueUnavailable:
                    result[key] = None
            return result

        current_all = {**known(self.current), **current}
        x_all = {**known(self.item_x), **x}
        y_all = {**known(self.item_y), **y}
        extra = [
            f
            for f in set(x_all) | set(y_all)
            if f not in fields and f != 'ScalingPercentPP'
        ]
        independent = compile_swap(current_all, x_all, y_all, extra)
        swap['PartDeltas'] = {**independent['PartDeltas'], **swap['PartDeltas']}
        values = {
            **independent['Values'],
            **swap['Values'],
            **self.overrides,
            'SelectedBranchID': self.branch_id,
            'ProfileOverrideBranchID': self.branch_id,
        }
        branches = []
        for row in self.branches():
            branches.append(
                Branch(
                    row['ComparisonBranchID'],
                    branch_profile(row),
                    offset_status=row.get('FixedOffsetStatus') or 'UNKNOWN',
                    offset_minimum=row.get('FixedOffsetMinimum'),
                    coefficient=row.get('ScalingCoefficientLevel1'),
                )
            )
        refs = []
        for row in self.catalog['GuideTargets']:
            belongs = (
                (row.get('BuildProfileID') == self.profile_id)
                if self.profile_id
                else row.get('CharacterID') == self.character_id
            )
            if not belongs:
                continue
            stat = row.get('StatID')
            mapping = {
                'STAT_CRIT_RATE': 'CritRatePP',
                'STAT_CRIT_DMG': 'CritDamagePP',
                'STAT_CYCLE_INTENSITY': 'CycleIntensity',
                'STAT_UNIVERSAL_DMG': 'UniversalPP',
            }
            if stat == {'ANG': 'STAT_ATK', 'LP': 'STAT_HP', 'VER': 'STAT_DEF'}.get(
                self.profile().get('ScalingStat')
            ):
                field = 'ScaleDirect'
            else:
                field = mapping.get(stat)
            refs.append(
                {
                    **row,
                    'TargetMinimum': row.get('Minimum'),
                    'TargetMaximum': row.get('Maximum') or row.get('RangeUpper'),
                    'BeforeValue': values.get('Before' + field) if field else None,
                    'AfterValue': values.get('After' + field) if field else None,
                    'ContextVerified': False,
                    'CurrentLevel': None,
                    'TargetLevel': row.get('TargetLevel'),
                }
            )
        engine = compare(values, self.release(), branches=branches, targets=refs)
        engine['Diagnostics'] = [*engine.get('Diagnostics', []), *swap['Diagnostics']]
        self.last_result = {
            'engine': engine,
            'current': current_all,
            'x': x_all,
            'y': y_all,
            'part_deltas': swap['PartDeltas'],
            'errors': errors,
            'guide': refs,
            'ark': self.ark_summary(),
            'profile': self.profile(),
        }
        return self.last_result

    def display(self):
        r = self.last_result or self.calculate()
        engine = r['engine']
        verdict = T.VERDICTS.get(engine.get('Verdict'), T.INDETERMINATE)
        lines = [verdict, T.NOT_DPS, T.ASSUMPTION, r['ark']]
        if (
            engine.get('OutputStatus') == 'READY'
            and engine.get('VerdictRatio') is not None
        ):
            lines.append('Verhältnis: ' + engine['VerdictRatio'].replace('.', ','))
        elif engine.get('RatioMin') is not None and engine.get('RatioMax') is not None:
            lines.append(
                'Mögliche Verhältnisse: '
                + engine['RatioMin'].replace('.', ',')
                + ' bis '
                + engine['RatioMax'].replace('.', ',')
            )
        for heading, group in (
            (T.CURRENT, r['current']),
            (T.PART_X, r['x']),
            (T.PART_Y, r['y']),
            (T.DIFFERENCE, r['part_deltas']),
            (T.TOTAL_DIFFERENCE, engine.get('Deltas', {})),
        ):
            lines += ['', heading]
            lines += [
                T.FIELD_LABELS.get(k, k) + ': ' + v.replace('.', ',')
                for k, v in group.items()
                if v is not None
            ]
            if not any(v is not None for v in group.values()):
                lines.append('Keine bekannten Werte in diesem Bereich.')
        lines += ['', T.GUIDE]
        if not r['guide']:
            lines.append(T.NO_GUIDE)
        for row in r['guide']:
            status = (
                T.GUIDE_WARNING
                if row.get('SourceStatus') == 'NOT_VERIFIED_FOR_1_5'
                else T.GUIDE_BASIS
            )
            label = {
                'STAT_ATK': 'ANG',
                'STAT_HP': 'LP',
                'STAT_DEF': 'VER',
                'STAT_CRIT_RATE': 'Krit-Rate',
                'STAT_CRIT_DMG': 'Krit-Schaden',
                'STAT_CYCLE_INTENSITY': 'Zyklusstärke',
            }.get(row.get('StatID'), 'Richtwert')
            lines.append(
                label
                + ': '
                + str(row.get('Minimum') or 'unbekannt')
                + ' '
                + str(row.get('Unit') or '')
                + ' · '
                + status
            )
            lines.append(
                'Quelle: '
                + str(row.get('Source') or row.get('SourceID') or 'unbekannt')
                + ' · '
                + str(row.get('RetrievedAtUTC') or 'Datum unbekannt')
            )
        lines += ['', T.HINTS, T.ARK_WARNING]
        lines += [key + ': ' + value for key, value in r['errors'].items()]
        for message in engine.get('Diagnostics', []):
            for field, label in sorted(
                T.FIELD_LABELS.items(), key=lambda pair: -len(pair[0])
            ):
                message = (
                    message.replace('Before' + field, label + ' aktuell')
                    .replace('After' + field, label + ' nach Tausch')
                    .replace(field, label)
                )
            lines.append(message)
        return '\n'.join(lines)
