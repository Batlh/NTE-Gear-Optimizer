# Calculation contracts — Phase 1B-1

In development; subject to independent review. No UI, combat simulation,
user-data import/export, new payload format or automatic gear decision.

## Authority and inputs

- OPB-10 decimal rounding is unchanged (PLATTFORM-11).
- Contract and dependency-local output rules precede legacy workbook behavior
  (PLATTFORM-15). ProfileType and ScalingStat are separate domains.
- Numbers are canonical decimal strings or null, not floats. Percent fields
  ending in PP are percentage points; ExtraBreakBuff is already a factor.
  Core adapters do not silently parse decimal commas or strip whitespace.
- Stable IDs carry identity. Labels do not. Release profiles/branches, source
  tables, ruleset registries and geometry are explicit trusted inputs, not
  writable calculated caches. User overrides are applied only to their bound
  branch. Unknown and null are distinct. EffectiveSource is derived.
- All pure modules are under src/nte_gear_optimizer. File access lives in tools
  and test adapters. The existing patch-1.5 data import stays unchanged.

## APIs and output scope

- models.profile_state: effective_profile, unique_reference, build_items_valid,
  ruleset_status. Reusing an item in separate comparison plans is allowed.
- validation.scoped: validate_selected requires real validator coverage;
  character_state, ark_progress and item_stats retain local unknowns; layout
  uses supplied native geometry and error phase precedence. No character mask
  assignments or intermediate item curves are guessed. Missing exact source
  points remain UNKNOWN. Native module mains are ATK and HP; stored locked
  substats are retained but do not count before their released unlock level.
- panels.resolution: atomic_atk requires an approved panel basis. DIRECT needs
  matching fingerprint/ruleset and capture/provenance/external declarations.
  No cache is promoted to an observation. Synthetic fixtures are forbidden in
  production and require explicit allow_synthetic=True for test execution.
- comparison.factors and robust_branches: enumerate all applicable unknown
  factors, then every released branch. Compare exact decimal quotients, never
  with an epsilon or a branch average. Unknown inputs and affine limitations
  restrict only their dependent recommendation, retaining known deltas/proxy.
- guide.reference: sourced, verified same-basis comparison; declared additive
  conversion only. First rank with a target-status change decides only for
  invariant/other scaling; it never overrides a known variable-scale product.
  Conditional target conflicts are unavailable, not first-row winners.
- comparison.recommendation.compare composes independent output blocks.
  optional target collision handling is a pure relation/quarantine check,
  not a file import or transaction implementation. ValidBuildCommit in the
  frozen vector is the scope assertion that the build remains valid, not an
  implemented persistent commit operation.
- projection.lv80.project is display-only. RAW_LEVEL_STAT is not a white basis.
  Missing equipment percent allows a minimum, not an invented exact value.
- legacy.item_score.score_item implements the frozen 60/40 heuristic. It is
  separate from the static performance comparison and does not require an Ark.

## Explicit limitations and provisional decisions

The 23 unsupported ACTUAL mode channels remain individually unavailable with
ERR_CHANNEL_MODE_NOT_SUPPORTED_V028. HP/DEF atomic formulas are not inferred
from ATK. Required exact source curves/geometry must be supplied, not guessed.
There is no rotation, combat timing, inventory optimizer or inferred cap.
FixedOffsetStatus UNKNOWN uses provisional decision A: proxy with visible
FIXED_OFFSET_STATUS_UNKNOWN, not an assumed zero offset. No new offset evidence
has been invented. Source-driven scope decisions are not a security boundary
against modifying both released data and engine code.

## Reproducible evidence

tests/fixtures/core_cases.json contains all 67 unchanged 1B-0 vectors, linked
to source TSV SHA-256 FFBFF0F1828520779E994FA2FC1C78A693262FEB06F1943FF3816CC2E65AE836.
Its test adapter chooses synthetic setup records only; production code never
branches on CaseID or reads expectations. The 12 earlier skipped groups now run.
The synthetic numbers are not observations from the game.

tests/fixtures/excel_goldens.json binds the accepted auditor source hash
1D0C586B9FD9289584150EE21687340382256FE16B0DC4D5008453204C49E168 and review hash
8507BA060F617B7B9B281717D21FFE99C4687F22D9C8F4B9346C1344476B5EA9.
Ten rows have native values, four remain contract-only because the workbook
cannot represent them. Native binary tails are compared through OPB-10.
The unverified-guide global gate and negative-scale legacy ratio are explicit
contract-over-workbook differences; expectations are not rewritten.

tests/fixtures/core_sources.json binds relevant N5D members and the frozen ZIP.
tests/fixtures/scoring_policy.json binds ScoringRules!A2:B6 of workbook hash
1D07965C6EC3C9652AAD8750B84EECD01E9EA168A8DF37C1E5A3386FDA2799AE.
Private local capture paths and screenshots are not redistributed in the repo.
MIT applies to our own code; original game/guide data retains its own provenance
and rights as explained in data/SOURCES.md.

Source mutations run in memory against the same semantic oracles; a syntax or
import failure is not counted as a killed mutation. Native/WebAssembly parity
compares every output including nulls, scope, provenance, intervals and diagnostics,
also under hostile ambient decimal precision/rounding. CI has no secrets.
