from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Iterable, Mapping

import requests

from .event_normalizer import NormalizedEvent, normalize_event


ZABBIX_SEVERITY = {
    0: "info",
    1: "info",
    2: "warning",
    3: "average",
    4: "high",
    5: "disaster",
}


@dataclass(frozen=True)
class Evidence:
    source: str
    source_event_id: str
    source_object_id: str
    observed_at: int


@dataclass(frozen=True)
class AdapterEvent:
    normalized: NormalizedEvent
    correlation_key: str
    evidence: Evidence


class ZabbixAdapter:
    """Small read-only adapter for active Zabbix problems."""

    def __init__(
        self,
        api_url: str,
        api_token: str,
        *,
        session: requests.Session | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.api_url = api_url
        self.api_token = api_token
        self.session = session or requests.Session()
        self.timeout = timeout

    def _rpc(self, method: str, params: Mapping[str, Any]) -> Any:
        response = self.session.post(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json-rpc",
            },
            json={"jsonrpc": "2.0", "method": method, "params": dict(params), "id": 1},
            timeout=self.timeout,
        )
        response.raise_for_status()
        body = response.json()
        if "error" in body:
            error = body["error"]
            message = error.get("message", "Zabbix API error")
            data = error.get("data", "")
            raise RuntimeError(f"{message}: {data}".strip())
        return body.get("result")

    def _problems(self, limit: int) -> list[dict[str, Any]]:
        return list(self._rpc("problem.get", {
            "output": ["eventid", "objectid", "name", "severity", "clock"],
            "recent": False,
            "sortfield": ["eventid"],
            "sortorder": "DESC",
            "limit": limit,
        }) or [])

    def _triggers(self, trigger_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        ids = sorted({str(value) for value in trigger_ids if value})
        if not ids:
            return {}
        rows = self._rpc("trigger.get", {
            "triggerids": ids,
            "output": ["triggerid", "description", "priority"],
            "selectHosts": ["hostid", "host", "name"],
        }) or []
        return {str(row["triggerid"]): row for row in rows}

    @staticmethod
    def _correlation_key(
        entity: str,
        source_object_id: str,
        problem_kind: str | None,
        message: str,
    ) -> str:
        stable_problem = problem_kind or " ".join(message.lower().split())
        material = f"zabbix|{entity.lower()}|{source_object_id}|{stable_problem}"
        return sha256(material.encode("utf-8")).hexdigest()

    def active_events(self, limit: int = 100) -> list[AdapterEvent]:
        problems = self._problems(limit)
        triggers = self._triggers(
            str(problem.get("objectid") or "") for problem in problems
        )
        events: list[AdapterEvent] = []

        for problem in problems:
            object_id = str(problem.get("objectid") or "")
            trigger = triggers.get(object_id, {})
            hosts = trigger.get("hosts") or []
            host = hosts[0] if hosts else {}
            entity = str(host.get("host") or host.get("name") or "unknown")
            message = str(problem.get("name") or trigger.get("description") or "")
            try:
                severity_id = int(problem.get("severity") or 0)
            except (TypeError, ValueError):
                severity_id = 0

            normalized = normalize_event("zabbix", {
                "host": entity,
                "message": message,
                "severity": ZABBIX_SEVERITY.get(severity_id, "unknown"),
            })

            event_id = str(problem.get("eventid") or "")
            try:
                observed_at = int(problem.get("clock") or 0)
            except (TypeError, ValueError):
                observed_at = 0

            events.append(
                AdapterEvent(
                    normalized=normalized,
                    correlation_key=self._correlation_key(
                        entity,
                        object_id,
                        normalized.problem_kind,
                        message,
                    ),
                    evidence=Evidence(
                        source="zabbix",
                        source_event_id=event_id,
                        source_object_id=object_id,
                        observed_at=observed_at,
                    ),
                )
            )

        return events
