# Release notes v5.77

## Verified plan source

A complete plan requires a real teacher on every currently required position in both
scopes. Row counts alone are not coverage. The snapshot audit also rejects a teacher
assigned twice in the same slot across scopes.

All plan-bearing UI surfaces use the same /api/effective-plan snapshot and source_id.
The source is explicitly one of live_verified, saved_verified, reference_verified or
invalid_saved. The durable data/last_good_plan.json is revalidated before use.

## Protected search stages

1. Hard/system constraints and complete coverage.
2. Ordinary pool moves, capacity and individual non-edge changes.
3. Remaining limits, group preferences and fairness.
4. WF emergency fallback.
5. after_last_long - long break after the teacher's final lesson.
6. avoid_wait - additional waiting, absolute last fallback.

WF is filtered from automatic initial pools. Explicit administrator-fixed WF assignments
remain valid. When stage 4 is unlocked, the search first repairs the best partial with
one WF teacher at a time. CP-SAT minimizes automatic WF assignments across both scopes
lexicographically. If stage 4 or earlier yields a verified full plan, after_last_long is
not unlocked merely to generate additional variants.

## Deployment gate

Deployment requires Python and JavaScript syntax checks, encoding regression, the full
unittest suite, a real-state effective-plan audit, identical source_id in diagnostics and
teacher portals, and a fresh solver search without stale variants from the prior policy.
