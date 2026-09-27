"""Deterministic correlation for normalized infrastructure events.

Public examples are synthetic. Source systems remain authoritative.
"""
from collections import defaultdict

def correlate(events: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for event in events:
        entity = str(event.get("entity", "")).strip().lower()
        kind = str(event.get("problem_kind", "unknown")).strip().lower()
        if not entity:
            continue
        grouped[(entity, kind)].append(event)

    issues = []
    for (entity, kind), members in grouped.items():
        sources = sorted({str(x.get("source", "unknown")).lower() for x in members})
        severity = max((int(x.get("severity", 0)) for x in members), default=0)
        evidence = [
            {"source": x.get("source"), "message": x.get("message"), "source_event_id": x.get("source_event_id")}
            for x in members
        ]
        issues.append({
            "entity": entity,
            "problem_kind": kind,
            "severity": severity,
            "sources": sources,
            "event_count": len(members),
            "evidence": evidence,
        })
    return sorted(issues, key=lambda x: (-x["severity"], x["entity"], x["problem_kind"]))
