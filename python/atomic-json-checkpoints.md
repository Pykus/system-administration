# Atomic JSON checkpoints for reliable Python automation

A scheduler that runs hourly needs to distinguish **completed work** from work that was merely started. A state file is often sufficient for a single-process worker, but a direct `write_text(json.dumps(...))` is not: a crash during writing can leave truncated JSON, and rerunning a task can duplicate side effects. This chapter implements an atomic checkpoint, schema validation, and a small idempotency ledger using only Python's standard library.

## When to use this pattern

Use a local JSON checkpoint for one worker on one host, small state (kilobytes rather than millions of records), and recoverable operations such as generating reports or uploading artifacts. Typical cases include remembering which lessons were published, tracking completed inventory scans, and resuming a batch after a restart. A checkpoint should store **evidence** such as a verified artifact URL or commit SHA, not just a boolean flag.

Do **not** use this design as a multi-host transaction database. Two writers can each read the same version and silently overwrite one another, even though each individual replacement is atomic. For concurrent writers use SQLite with transactions or a server-side database. For financial transfers, purchases, and non-idempotent external APIs, use provider idempotency keys or a transactional outbox; a local JSON file cannot make the remote action and the checkpoint one atomic transaction.

## Complete implementation

Save this as `checkpoint_store.py`. The temporary file is created in the **same directory** as the destination, which is important because `os.replace` is intended for atomic replacement on the same filesystem. The file is flushed and synced before replacement. On POSIX systems the parent directory is also synced when supported; Windows may not expose directory fsync. Atomic visibility is not an absolute guarantee against all power-loss and storage-controller failures.

```python
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = 1


def empty_state() -> dict[str, Any]:
    return {"schema": SCHEMA, "completed": {}}


def validate(state: object) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise ValueError("Checkpoint must be an object")
    if state.get("schema") != SCHEMA:
        raise ValueError("Unsupported checkpoint schema")
    completed = state.get("completed")
    if not isinstance(completed, dict):
        raise ValueError("completed must be an object")
    for key, record in completed.items():
        if not isinstance(key, str) or not isinstance(record, dict):
            raise ValueError("Invalid completed entry")
        if not isinstance(record.get("evidence"), str) or not record["evidence"]:
            raise ValueError("Each completion needs nonempty evidence")
    return state


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_state()
    # Fail closed: never silently overwrite a corrupt checkpoint.
    with path.open("r", encoding="utf-8") as handle:
        return validate(json.load(handle))


def save_state(path: Path, state: dict[str, Any]) -> None:
    validate(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(state, ensure_ascii=False, indent=2,
                          sort_keys=True) + "\n").encode("utf-8")
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.",
            suffix=".tmp", delete=False
        ) as handle:
            temporary = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        if os.name == "posix":
            try:
                descriptor = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            except OSError:
                pass  # Filesystem may not support directory fsync.
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def mark_complete(path: Path, task_id: str, evidence: str) -> bool:
    if not task_id or not evidence:
        raise ValueError("task_id and evidence are required")
    state = load_state(path)
    if task_id in state["completed"]:
        return False  # Already recorded; do not repeat the side effect.
    state["completed"][task_id] = {
        "evidence": evidence,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
    save_state(path, state)
    return True
```

The `mark_complete` function records a **verified** completion, not an intent. An external workflow must first perform its action, read the remote result back, and only then call `mark_complete`. When the worker restarts, it checks `load_state(path)["completed"]` before repeating the operation. If the remote action succeeded but the process crashed before checkpointing, reconcile with the remote system using the task ID before retrying.

## Example workflow and tests

An upload worker could use the lesson identifier as `task_id` and the actual uploaded document URL as `evidence`. A GitHub publishing worker could use `2026-10-08:python` and a verified commit URL. Avoid placing access tokens or student data in the checkpoint.

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from checkpoint_store import load_state, mark_complete, save_state

with TemporaryDirectory() as directory:
    path = Path(directory) / "checkpoint.json"
    assert load_state(path)["completed"] == {}
    assert mark_complete(path, "lesson-04", "https://example.org/artifact/4")
    assert not mark_complete(path, "lesson-04", "https://example.org/artifact/4")
    assert len(load_state(path)["completed"]) == 1

    # Simulate an interrupted write by leaving a stray temp file.
    (path.parent / ".checkpoint.json.abandoned.tmp").write_text("partial")
    assert len(load_state(path)["completed"]) == 1

    # A malformed checkpoint must not be treated as an empty state.
    path.write_text("{broken", encoding="utf-8")
    try:
        load_state(path)
    except ValueError:  # JSONDecodeError subclasses ValueError.
        pass
    else:
        raise AssertionError("Corrupt state was silently accepted")
print("checkpoint tests passed")
```

Run `python -m compileall -q checkpoint_store.py`, then `python test_checkpoint.py` after saving the second block as `test_checkpoint.py`. Repeat the test on the actual operating system and filesystem used by the worker. In production, also test restart after a deliberately killed worker, file permission errors, disk-full errors, and recovery from a saved backup.

## Failure modes and operational decisions

**Truncated or malformed JSON:** do not reset automatically. Quarantine the file, inspect a backup, and reconcile remote evidence before resuming. **Wrong schema:** stop and perform an explicit migration, preserving the previous version. **Concurrent writes:** atomic replacement prevents partial reads, not lost updates; enforce a single-writer lease or move to SQLite. **Remote success before local save:** query the remote system before retrying; do not trust a local `False`/missing key as proof the remote action did not happen. **File permissions or antivirus interference:** `os.replace` may raise; the previous destination remains intact and the worker must report failure.

A useful checkpoint answers three questions: *what completed, how was completion verified, and can a restart safely decide what to do next?* Keep the state small, make corruption visible, and never confuse a successfully written checkpoint with a successfully verified external operation.
