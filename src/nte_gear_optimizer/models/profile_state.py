"""OPB-01/03/04: stable identity and field-local, branch-bound profiles.

No labels, calculated caches or caller-supplied EffectiveSource are trusted.
"""

from dataclasses import dataclass
from typing import Mapping, Any

DOMAINS = {
    'ProfileType': frozenset(('DAMAGE', 'HEAL', 'SHIELD', 'BUFF', 'UNKNOWN')),
    'ScalingStat': frozenset(
        ('ANG', 'LP', 'VER', 'BASIS_ANG', 'SONSTIGE', 'UNBEKANNT')
    ),
    'CritEligible': frozenset(('TRUE', 'FALSE', 'UNKNOWN')),
    'BreakEligible': frozenset(('TRUE', 'FALSE', 'UNKNOWN')),
    'CycleType': frozenset(
        ('NONE', 'BLOSSOM', 'NOVA', 'SCORCH', 'HEXED', 'STAIN', 'UNKNOWN')
    ),
}
FIELDS = tuple(DOMAINS) + (
    'ScalingEvidenceStatus',
    'ScalingEvidence',
    'DamageElementStatID',
    'DamageSourceCategory',
    'ScalingMechanismName',
)


@dataclass(frozen=True)
class EffectiveProfile:
    values: Mapping[str, Any]
    sources: Mapping[str, str]
    diagnostics: tuple[str, ...]


def effective_profile(
    release: Mapping, overrides: Mapping, *, branch_id=None, override_branch_id=None
) -> EffectiveProfile:
    values, sources, diagnostics = {}, {}, []
    bound = override_branch_id == branch_id
    for field in FIELDS:
        value = overrides.get(field) if bound else None
        if value is not None and field in DOMAINS and value not in DOMAINS[field]:
            diagnostics.append('Ungültiger optionaler Wert: ' + field)
            value = None
        values[field] = release.get(field) if value is None else value
        sources[field] = 'RELEASE' if value is None else 'USER'
    return EffectiveProfile(values, sources, tuple(diagnostics))


def unique_reference(rows, key, value):
    """Resolve only the requested identity. Unused bad rows do not gate it."""
    found = [r for r in rows if r.get(key) == value]
    return found[0] if value is not None and len(found) == 1 else None


def build_items_valid(item_ids):
    """Ownership is not exclusive across comparison plans; check one build."""
    return len(item_ids) == len(set(item_ids))


def ruleset_status(registry, ruleset_id, revision):
    row = unique_reference(registry, 'RulesetID', ruleset_id)
    if row is None or row.get('Revision') != revision:
        return 'UNKNOWN'
    return (
        row.get('Status')
        if row.get('Status') in ('CURRENT', 'SUPERSEDED')
        else 'UNKNOWN'
    )
