"""Kivy-free presentation state; calculations are delegated to the pure core."""

from decimal import Decimal
import re
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


class InputFormatError(ValueUnavailable):
    def __init__(self, hint):
        self.hint = hint
        super().__init__('Eingabe', True)


def numeric_hint(value):
    try:
        parsed = normalize(value)
    except ValueUnavailable as error:
        return getattr(error, 'hint', T.MESSAGES['invalid'])
    if parsed is not None and (
        re.search(r',\d{3}$', value.strip())
        or any(c in value.strip() for c in (' ', '\u00a0', '\u202f'))
    ):
        return 'übernommen als ' + parsed.replace('.', ',')
    return ''


def normalize(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueUnavailable('Eingabe', True)
    value = value.replace('\u00a0', ' ').replace('\u202f', ' ').strip()
    if any(c.isspace() for c in value):
        if not re.fullmatch(r'[+-]?[0-9]{1,3}( [0-9]{3})+(,[0-9]+)?', value):
            raise InputFormatError(
                'Bitte Leerzeichen nur in Dreiergruppen verwenden, z. B. 2 560 – sonst ohne Leerzeichen eingeben.'
            )
        value = value.replace(' ', '')
    if '.' in value:
        if re.fullmatch(r'[+-]?[0-9]{1,3}(?:\.[0-9]{3})+', value.split(',')[0]):
            raise InputFormatError(T.THOUSANDS_HINT)
        raise InputFormatError(T.DECIMAL_HINT)
    value = value.replace(',', '.')
    if not value:
        return None
    result = number(value)
    return '0' if result == 0 else text(result)


ARK_LEVEL_HINT = 'Bitte ganze Zahl von 1 bis 80 eingeben (oder leer lassen)'


def ark_level_hint(value):
    value = value.strip()
    if not value:
        return ''
    # ASCII integer syntax only; pasted emoji/Unicode numerals are not levels.
    if not re.fullmatch(r'[0-9]{1,3}', value) or not 1 <= int(value) <= 80:
        return ARK_LEVEL_HINT
    return ''


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
            self.white_panel_base = ''
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

    def input_scaling_stat(self):
        if self.branches() and self.branch_id is None:
            scales = {r.get('ScalingStat') for r in self.branches()} & {
                'ANG',
                'LP',
                'VER',
            }
            return next(iter(scales)) if len(scales) == 1 else 'UNBEKANNT'
        return self.profile().get('ScalingStat')

    def ambiguous_scaling(self):
        return (
            self.branch_id is None
            and len(
                {r.get('ScalingStat') for r in self.branches()} & {'ANG', 'LP', 'VER'}
            )
            > 1
        )

    def fields(self):
        if self.branches() and self.branch_id is None:
            result = list(
                dict.fromkeys(
                    f
                    for b in self.branches()
                    for f in self.fields_for(branch_profile(b))
                )
            )
            if self.ambiguous_scaling():
                result = [f for f in result if f != 'ScaleDirect']
            return result
        return self.fields_for(self.profile())

    def groups(self, parts=False):
        active = self.fields()
        result = {}
        for name, fields in [
            ('scale', ['ScaleDirect']),
            (
                'bonus',
                ['UniversalPP', 'ElementPP', 'SkillPP', 'OtherPP', 'ReductionPP'],
            ),
            ('crit', ['CritRatePP', 'CritDamagePP']),
            ('break', ['Break', 'ExtraBreakBuff']),
            ('cycle', ['CycleIntensity']),
            ('heal', ['HealingPP']),
            ('shield', ['ShieldPP']),
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
        if ark_level_hint(self.ark_level):
            return T.MESSAGES['ark_invalid'] + ' · ' + ARK_LEVEL_HINT
        if row is None:
            return T.NO_CHOICE
        level = self.ark_level.strip()
        if (
            level
            and int(level) == 80
            and row['ArkID'] in self.catalog['Decisions']['R15-04']['arks']
        ):
            return (
                row['ArkName']
                + T.MESSAGES['ark80']
                + self.catalog['Decisions']['R15-04']['base_atk']
                + T.MESSAGES['ark_authority']
            )
        return (
            row['ArkName']
            + T.MESSAGES['ark_level']
            + (self.ark_level.strip() or T.NO_CHOICE)
            + T.MESSAGES['ark_unknown']
        )

    def needs_white_base(self):
        try:
            before = normalize(self.item_x.get('ScalingPercentPP'))
            after = normalize(self.item_y.get('ScalingPercentPP'))
            return before is not None and after is not None and before != after
        except ValueUnavailable:
            return False

    def calculate(self):
        fields = self.fields()
        errors = {}

        def parsed(group, prefix, active):
            result = {}
            for field in active:
                try:
                    result[field] = normalize(group.get(field))
                except ValueUnavailable as error:
                    result[field] = None
                    errors[prefix + ' ' + T.FIELD_LABELS.get(field, field)] = getattr(
                        error, 'hint', T.MESSAGES['invalid']
                    )
            return result

        part_fields = fields + (['ScalingPercentPP'] if 'ScaleDirect' in fields else [])
        current = parsed(self.current, T.CURRENT, fields)
        x = parsed(self.item_x, T.PART_X, part_fields)
        y = parsed(self.item_y, T.PART_Y, part_fields)
        try:
            white = normalize(self.white_panel_base)
        except ValueUnavailable as error:
            white = None
            errors[T.FIELD_LABELS['WhitePanelBase']] = getattr(
                error, 'hint', T.MESSAGES['invalid']
            )
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
        if self.ambiguous_scaling():
            # A generic scalar cannot mean ANG and LP/VER simultaneously.
            # Preserve entered numbers/deltas as evidence, but do not feed a
            # mislabeled scalar into any branch's performance calculation.
            values['BeforeScaleDirect'] = None
            values['AfterScaleDirect'] = None
            swap['Diagnostics'].append(T.MESSAGES['select_branch_scale'])
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
        branch_notes = []
        for index, branch in enumerate(engine.get('BranchEvaluations', []), 1):
            branch_notes.extend(
                T.MESSAGES['branch'] + str(index) + ': ' + message
                for message in branch.get('Diagnostics', [])
            )
            hint = T.BRANCH_HINTS.get(branch.get('AffineStatus'))
            if hint:
                branch_notes.append(T.MESSAGES['branch'] + str(index) + ': ' + hint)
        engine['Diagnostics'] = [
            *engine.get('Diagnostics', []),
            *branch_notes,
            *swap['Diagnostics'],
        ]
        self.last_result = {
            'engine': engine,
            'current': current_all,
            'x': x_all,
            'y': y_all,
            'part_deltas': swap['PartDeltas'],
            'white_panel_base': white,
            'resolved': {
                k: v for k, v in values.items() if k.startswith(('Before', 'After'))
            },
            'errors': errors,
            'guide': refs,
            'ark': self.ark_summary(),
            'profile': self.profile(),
            'input_scaling': self.input_scaling_stat(),
        }
        return self.last_result

    def _full_display(self, show_all=True):
        r = self.last_result or self.calculate()
        engine = r['engine']
        verdict = T.VERDICTS.get(engine.get('Verdict'), T.INDETERMINATE)
        lines = [verdict, T.NOT_DPS, T.ASSUMPTION, r['ark']]
        if engine.get('OutputStatus') != 'READY':
            lines.append(
                T.STATUS_HINTS.get(
                    engine.get('OutputStatus'), T.MESSAGES['status_unknown']
                )
            )
        if engine.get('BaseProxyRatio') is not None:
            lines.append(
                T.MESSAGES['proxy'] + engine['BaseProxyRatio'].replace('.', ',')
            )
        if (
            engine.get('OutputStatus') == 'READY'
            and engine.get('VerdictRatio') is not None
        ):
            lines.append(T.MESSAGES['ratio'] + engine['VerdictRatio'].replace('.', ','))
        elif engine.get('RatioMin') is not None and engine.get('RatioMax') is not None:
            lines.append(
                T.MESSAGES['range']
                + engine['RatioMin'].replace('.', ',')
                + T.MESSAGES['to']
                + engine['RatioMax'].replace('.', ',')
            )
        changed = {
            key
            for group in (r['part_deltas'], engine.get('Deltas', {}))
            for key, value in group.items()
            if value is not None and Decimal(value) != 0
        }
        for heading, group in (
            (T.CURRENT, r['current']),
            (T.PART_X, r['x']),
            (T.PART_Y, r['y']),
            (T.DIFFERENCE, r['part_deltas']),
            (T.TOTAL_DIFFERENCE, engine.get('Deltas', {})),
        ):
            lines += ['', heading]
            lines += [
                T.field_label(
                    k,
                    r['input_scaling'],
                    parts=heading in (T.PART_X, T.PART_Y, T.DIFFERENCE),
                )
                + ': '
                + v.replace('.', ',')
                for k, v in group.items()
                if v is not None and (show_all or k in changed)
            ]
            if not any(v is not None for v in group.values()):
                lines.append(T.MESSAGES['empty'])
        if r['white_panel_base'] is not None and (
            show_all or 'ScalingPercentPP' in changed
        ):
            lines.append(
                T.FIELD_LABELS['WhitePanelBase']
                + ': '
                + r['white_panel_base'].replace('.', ',')
            )
        lines += ['', T.AFTER_TOTALS]
        for key, value in r['resolved'].items():
            if (
                key.startswith('After')
                and value is not None
                and (show_all or key[5:] in changed)
            ):
                lines.append(
                    T.field_label(key[5:], r['input_scaling'], after=True)
                    + ': '
                    + value.replace('.', ',')
                )
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
                T.MESSAGES['source']
                + str(row.get('Source') or row.get('SourceID') or 'unbekannt')
                + ' · '
                + str(row.get('RetrievedAtUTC') or T.MESSAGES['unknown_date'])
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
            lines.append(
                message.replace('Teil X', T.PART_X).replace('Teil Y', T.PART_Y)
            )
        return '\n'.join(lines)

    def display(self):
        """Complete accessible values; kept for diagnostics and compatibility."""
        return self._full_display(show_all=True)

    def details_display(self, show_all=False):
        result = self.last_result or self.calculate()
        undecided = result['engine'].get('Verdict') is None
        full = self._full_display(show_all=show_all or undecided)
        return full[full.index('\n' + T.CURRENT + '\n') + 1 :]

    def jump_to(self, step):
        if step not in (0, 1, 2):
            raise ValueError('Unbekannter Eingabeschritt')
        self.step = step

    @staticmethod
    def localized_diagnostic(message):
        for field, label in sorted(
            T.FIELD_LABELS.items(), key=lambda pair: -len(pair[0])
        ):
            message = (
                message.replace('Before' + field, label + ' aktuell')
                .replace('After' + field, label + ' nach Tausch')
                .replace(field, label)
            )
        return message.replace('Teil X', T.PART_X).replace('Teil Y', T.PART_Y)

    def missing_groups(self):
        """Route only actual core diagnostics/local parse errors to their inputs.

        Missing resolved After values may come from current OR either part;
        route to the raw input that is absent, not blindly to the parts page.
        Branch applicability and branch-selection diagnoses belong to selection.
        """
        r = self.last_result or self.calculate()
        if r['engine'].get('Verdict') is not None:
            return []
        groups = {0: [], 1: [], 2: []}
        selection = (
            'ProfileType',
            'ScalingStat',
            'CritEligible',
            'BreakEligible',
            'CycleType',
            'BuildProfileID',
            'SelectedBranchID',
        )
        for message in r['engine'].get('Diagnostics', []):
            targets = set()
            if (
                any(key in message for key in selection)
                or message == T.MESSAGES['select_branch_scale']
            ):
                targets.add(0)
            for field in T.FIELD_LABELS:
                if field not in message or field in selection:
                    continue
                if (
                    'Teil X:' in message
                    or 'Teil Y:' in message
                    or field == 'WhitePanelBase'
                ):
                    targets.add(2)
                elif 'Aktuell:' in message or 'Before' + field in message:
                    targets.add(1)
                else:
                    for group, step in [('current', 1), ('x', 2), ('y', 2)]:
                        if r[group].get(field) is None:
                            targets.add(step)
            if not targets:
                # Non-field core causes (branch disagreement/affine limits)
                # stay explicit and direct the user to branch selection.
                targets.add(0)
            localized = self.localized_diagnostic(message)
            for step in targets:
                if localized not in groups[step]:
                    groups[step].append(localized)
        for label, hint in r['errors'].items():
            step = (
                2
                if label.startswith((T.PART_X, T.PART_Y))
                or label == T.FIELD_LABELS['WhitePanelBase']
                else 1
            )
            groups[step].append(label + ': ' + hint)
        if ark_level_hint(self.ark_level):
            groups[0].append('Ark-Level: ' + ARK_LEVEL_HINT + ' (nicht übernommen)')
        merged = {}
        for step, messages in groups.items():
            combined = {}
            for message in messages:
                # Use the longest known label first (e.g. scaling total vs
                # scaling percentage); do not merge different fields.
                field = next(
                    (
                        key
                        for key, label in sorted(
                            T.FIELD_LABELS.items(), key=lambda pair: -len(pair[1])
                        )
                        if label in message
                    ),
                    None,
                )
                if field is None:
                    combined.setdefault(('other', message), message)
                    continue
                label = T.field_label(field, r['input_scaling'], parts=step == 2)
                message = message.replace(T.FIELD_LABELS[field], '').strip(' :')
                key = ('field', field)
                # Keep separate part-side evidence in a single field row.
                if key in combined:
                    if message not in combined[key]:
                        combined[key] += ' | ' + message
                else:
                    combined[key] = label + ': ' + message
            merged[step] = list(combined.values())
        return [(step, messages) for step, messages in merged.items() if messages]

    def clarification_display(self):
        r = self.last_result or self.calculate()

        def value(group, raws, field):
            parsed = group.get(field)
            if parsed is not None:
                return parsed.replace('.', ',')
            raw = raws.get(field)
            return raw + T.UNPARSED if raw else 'fehlt'

        lines = [T.EXPLANATION_VALUES]
        for field in self.fields() + (
            ['ScalingPercentPP'] if 'ScaleDirect' in self.fields() else []
        ):
            parts = (
                'Teile '
                + value(r['x'], self.item_x, field)
                + ' → '
                + value(r['y'], self.item_y, field)
            )
            # Percentage-on-part has no current-total input. Do not invent a
            # missing current value for a field that exists only on the parts.
            current = (
                ''
                if field == 'ScalingPercentPP'
                else 'aktuell ' + value(r['current'], self.current, field) + ' · '
            )
            lines.append(
                T.field_label(field, r['input_scaling']) + ': ' + current + parts
            )
        return '\n'.join(lines)

    def compact_display(self):
        r = self.last_result or self.calculate()
        engine = r['engine']
        scale = r['input_scaling']
        lines = [T.VERDICTS.get(engine.get('Verdict'), T.INDETERMINATE)]
        if (
            engine.get('VerdictRatio') is not None
            and engine.get('OutputStatus') == 'READY'
        ):
            lines.append(T.MESSAGES['ratio'] + engine['VerdictRatio'].replace('.', ','))
        elif engine.get('RatioMin') is not None and engine.get('RatioMax') is not None:
            lines.append(
                T.MESSAGES['range']
                + engine['RatioMin'].replace('.', ',')
                + T.MESSAGES['to']
                + engine['RatioMax'].replace('.', ',')
            )
        elif engine.get('Verdict') is not None:
            lines.append(T.NO_SINGLE_RATIO)
        if engine.get('Verdict') is None:
            lines += [
                T.STATUS_HINTS.get(
                    engine.get('OutputStatus'), T.MESSAGES['status_unknown']
                ),
                '',
                'Was fehlt',
            ]
            for step, messages in self.missing_groups():
                lines.append(T.STEPS[step])
                lines.extend(messages)
        lines += ['', T.CHANGED]
        count = 0
        for key, value in engine.get('Deltas', {}).items():
            if value is not None and Decimal(value) != 0:
                before = r['resolved'].get('Before' + key)
                after = r['resolved'].get('After' + key)
                label = (
                    T.SCALE_NAMES.get(scale, 'Skalierung')
                    if key == 'ScaleDirect'
                    else T.FIELD_LABELS.get(key, key)
                )
                transition = (before or T.NO_CHOICE) + ' → ' + (after or T.NO_CHOICE)
                lines.append(
                    label
                    + ': '
                    + transition.replace('.', ',')
                    + ' (Δ '
                    + value.replace('.', ',')
                    + ')'
                )
                count += 1
        for key, value in r['part_deltas'].items():
            if (
                value is not None
                and Decimal(value) != 0
                and (
                    engine.get('Deltas', {}).get(key) is None
                    or Decimal(engine['Deltas'][key]) != Decimal(value)
                )
            ):
                lines.append(
                    T.field_label(key, scale, parts=True)
                    + ': Δ '
                    + value.replace('.', ',')
                )
                count += 1
        if not count:
            lines.append(T.NO_CHANGES)
        if engine.get('OutputStatus') != 'READY' and engine.get('Verdict') is not None:
            lines.append(
                T.STATUS_HINTS.get(
                    engine.get('OutputStatus'), T.MESSAGES['status_unknown']
                )
            )
        if engine.get('BaseProxyRatio') is not None:
            lines.append(
                T.MESSAGES['proxy'] + engine['BaseProxyRatio'].replace('.', ',')
            )
        if r['guide']:
            lines += ['', 'Guide']
            lines.append(
                T.GUIDE_WARNING
                if any(
                    row.get('SourceStatus') == 'NOT_VERIFIED_FOR_1_5'
                    for row in r['guide']
                )
                else T.GUIDE_BASIS
            )
        # Explanations are never inside the collapsible value section.
        full = self._full_display()
        lines += ['', full[full.index('\n' + T.HINTS + '\n') + 1 :]]
        return '\n'.join(lines)
