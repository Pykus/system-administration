"""Constraint architecture contract for the duty planner.

The purpose is to keep future features in the cheapest correct layer:
- candidate_filter: unary/local eligibility decided before CP-SAT variables are useful
- preflight: cheap necessary-condition proofs/explanations, never full optimisation
- cp_sat_hard: relational or aggregate feasibility
- cp_sat_lexicographic: structural preference solved as a dedicated stage
- cp_sat_soft: weighted optimisation after structural priorities
- post_guard: defensive validation/ranking, never the primary implementation
"""

VALID_LAYERS={
    "candidate_filter","preflight","cp_sat_hard","cp_sat_lexicographic",
    "cp_sat_soft","post_guard","repair_lexicographic",
}

CONSTRAINT_ARCHITECTURE={
    "no_lesson_overlap":{
        "primary_layer":"candidate_filter","supporting_layers":["post_guard"],
        "reason":"Teacher-position edge is individually impossible when it overlaps a lesson."
    },
    "one_place_per_slot":{
        "primary_layer":"cp_sat_hard","supporting_layers":["post_guard"],
        "reason":"Requires coupling all simultaneous position variables for one teacher."
    },
    "cross_scope_conflict":{
        "primary_layer":"cp_sat_hard","supporting_layers":["post_guard"],
        "reason":"Couples 1-3 and whole-school assignments in the same slot."
    },
    "manual_blocks":{
        "primary_layer":"candidate_filter","supporting_layers":["post_guard"],
        "reason":"Admin block makes a single teacher-position edge illegal."
    },
    "preserve_school_current":{
        "primary_layer":"repair_lexicographic","supporting_layers":["cp_sat_soft"],
        "reason":"In repair mode minimise changed positions before ordinary comfort costs."
    },
    "max_day_13":{
        "primary_layer":"cp_sat_hard","supporting_layers":["preflight","post_guard"],
        "reason":"Aggregate daily capacity; preflight may prove capacity shortage but must not optimise it."
    },
    "max_day_school":{
        "primary_layer":"cp_sat_hard","supporting_layers":["preflight","post_guard"],
        "reason":"Aggregate daily capacity across school positions."
    },
    "max_week":{
        "primary_layer":"cp_sat_hard","supporting_layers":["preflight","post_guard"],
        "reason":"Aggregate weekly human-capacity limit."
    },
    "prefer_home_group":{
        "primary_layer":"cp_sat_lexicographic","supporting_layers":["post_guard"],
        "reason":"After full coverage minimise foreign-group assignments; outsiders remain legal fallback."
    },
    "balance_day":{
        "primary_layer":"cp_sat_soft","supporting_layers":[],
        "reason":"Quality preference across a teacher's daily assignment count."
    },
    "balance_week":{
        "primary_layer":"cp_sat_soft","supporting_layers":[],
        "reason":"Low-priority spreading tie-breaker; fairness remains proportional to lesson load."
    },
    "max_long_day":{
        "primary_layer":"cp_sat_hard","supporting_layers":["preflight","post_guard"],
        "reason":"Aggregate human-capacity limit for long breaks per day."
    },
    "max_long_week":{
        "primary_layer":"cp_sat_hard","supporting_layers":["preflight","post_guard"],
        "reason":"Aggregate human-capacity limit for long breaks per week."
    },
    "after_last_short":{
        "primary_layer":"candidate_filter","supporting_layers":["preflight","cp_sat_soft"],
        "reason":"Edge-of-day relation is local; hard excludes the edge, soft assigns an edge cost."
    },
    "after_last_long":{
        "primary_layer":"candidate_filter","supporting_layers":["preflight","cp_sat_soft"],
        "reason":"Edge-of-day relation is local; preflight can prove unavoidable exceptions."
    },
    "preference_grid":{
        "primary_layer":"cp_sat_soft","supporting_layers":["candidate_filter"],
        "reason":"Per-edge prefer/avoid score is cheap to compute before adding its objective coefficient."
    },
    "zone_transition_penalty":{
        "primary_layer":"cp_sat_soft","supporting_layers":["candidate_filter"],
        "reason":"Per-edge distance can be precomputed; CP-SAT chooses the globally best combination."
    },
    "before_first_short":{
        "primary_layer":"candidate_filter","supporting_layers":["preflight","cp_sat_soft"],
        "reason":"Local edge-of-day relation; soft form belongs in objective."
    },
    "before_first_long":{
        "primary_layer":"candidate_filter","supporting_layers":["preflight","cp_sat_soft"],
        "reason":"Local edge-of-day relation; preflight can prove unavoidable exceptions."
    },
    "lesson_load_fairness":{
        "primary_layer":"cp_sat_soft","supporting_layers":["post_guard"],
        "reason":"Global proportional target depends on all assignments; post guard only rejects pathological drafts."
    },
    "max_consecutive_duties":{
        "primary_layer":"cp_sat_hard","supporting_layers":["preflight","post_guard"],
        "reason":"Window constraint across adjacent breaks; preflight may prove unavoidable pressure."
    },
    "offday_duty":{
        "primary_layer":"candidate_filter","supporting_layers":["post_guard"],
        "reason":"Day has no lessons for that teacher, so the edge is locally illegal when hard."
    },
    "avoid_wait":{
        "primary_layer":"candidate_filter","supporting_layers":["preflight","cp_sat_soft","post_guard"],
        "reason":"Wait is computable per edge; hard removes it, soft penalises it; >=2 lesson waits remain system-illegal."
    },
}

def audit_constraint_architecture(actual_keys):
    actual=set(actual_keys)
    registered=set(CONSTRAINT_ARCHITECTURE)
    bad_layers=[]
    for key,row in CONSTRAINT_ARCHITECTURE.items():
        layers={row.get("primary_layer"),*row.get("supporting_layers",[])}
        invalid=sorted(x for x in layers if x not in VALID_LAYERS)
        if invalid: bad_layers.append({"key":key,"invalid_layers":invalid})
    return {
        "ok":actual==registered and not bad_layers,
        "missing_registry":sorted(actual-registered),
        "stale_registry":sorted(registered-actual),
        "bad_layers":bad_layers,
        "count_actual":len(actual),
        "count_registered":len(registered),
    }
