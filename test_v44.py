import os, sys

base=os.environ.get("PLANNER_TEST_BASE","").rstrip("/")
PRODUCTION={"http://127.0.0.1:8091","http://localhost:8091"}

if not base:
    raise SystemExit(
        "Legacy integration test disabled by default. "
        "Set PLANNER_TEST_BASE to an isolated test instance."
    )
if base in PRODUCTION:
    raise SystemExit("REFUSING TO RUN AGAINST PRODUCTION PORT 8091.")

raise SystemExit(
    "This legacy destructive integration script is quarantined. "
    "Its behavior is covered by tests/test_v5602_inactive_13_guard.py."
)
