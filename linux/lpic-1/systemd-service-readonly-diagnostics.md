# Diagnose a failing systemd service without changing its state (LPIC-1)

## Purpose and decision boundary

On a Linux server, a service may be `failed`, repeatedly restarting, inactive after boot, or apparently active while the application is unreachable. The first task is to **collect evidence without changing the incident**. Restarting too early can erase transient clues, hide a dependency problem, or cause an additional outage. This chapter covers read-only systemd triage suitable for LPIC-1 practice and cautious production incident response.

Use these checks for SSH, web servers, monitoring agents, scheduled daemons and custom services managed by systemd. Do not assume they apply to containers without systemd as PID 1, SysV-only systems, or services controlled by a separate supervisor. This procedure is not a repair script: it intentionally avoids `restart`, `enable`, `daemon-reload`, editing unit files or changing firewall rules.

## A complete read-only diagnostic script

Save the following as `service-triage.sh`, then run `bash -n service-triage.sh` to check syntax. Supply an actual service unit name; the input validation prevents arbitrary command options or unexpected unit types.

```bash
#!/usr/bin/env bash
set -u
if [[ $# -ne 1 ]]; then
  echo "Usage: $0 UNIT.service" >&2
  exit 2
fi
unit="$1"
if [[ ! "$unit" =~ ^[a-zA-Z0-9_.@:-]+\.service$ ]]; then
  echo "Expected a .service unit name" >&2
  exit 2
fi
printf '\n=== Host and unit ===\n'
hostname
printf 'Unit: %s\n' "$unit"
printf '\n=== State ===\n'
systemctl is-active "$unit" || true
systemctl is-enabled "$unit" || true
systemctl is-failed "$unit" || true
printf '\n=== Selected properties ===\n'
systemctl show "$unit" --no-pager \
  -p LoadState -p ActiveState -p SubState -p UnitFileState \
  -p Result -p ExecMainCode -p ExecMainStatus -p NRestarts \
  -p FragmentPath -p DropInPaths -p After -p Requires -p Wants || true
printf '\n=== Recent journal; inspect privately ===\n'
journalctl -u "$unit" -n 25 --no-pager --output=short-iso || true
printf '\n=== Startup dependency chain ===\n'
systemd-analyze critical-chain "$unit" || true
printf '\nCollection complete; no service state was changed.\n'
```

Run it with `bash service-triage.sh ssh.service` on Debian/Ubuntu or with the appropriate installed unit name on another distribution. A unit may be called `sshd.service` instead of `ssh.service`; check `systemctl list-unit-files --type=service` before assuming a name. Use an ordinary account where possible. Journal access may be restricted; insufficient permission is a **collection limitation**, not evidence that no errors exist. Avoid copying raw journal output to public issues or repositories because application logs can contain tokens, personal data and internal hostnames.

## How to interpret the evidence

`LoadState=not-found` means systemd cannot load that unit under the supplied name. Verify the package and unit naming before considering any repair. `ActiveState=active` means systemd considers the unit active, but it does **not** prove that a network endpoint, database or business transaction works. Always add an application-level health check from an appropriate host.

`Result=exit-code` and `ExecMainStatus` provide a clue about how the main process ended. Exit code 1 alone is not a diagnosis: the journal and application-specific documentation are needed. A growing `NRestarts` suggests a restart loop, but its interpretation depends on the unit's restart policy and systemd version. `UnitFileState=disabled` does not necessarily mean a unit is broken: it may be started by a socket, timer, dependency or administrator.

The dependency graph requires care. `After=` controls ordering; it does not by itself pull another unit into the transaction. `Requires=` establishes a stronger dependency, while `Wants=` is weaker. A unit can start after another unit even if the latter is not required. `systemd-analyze critical-chain` shows ordering and timing context, not a universal explanation for every delay. Cross-check the timestamps in `journalctl` and any related units.

## Three incident scenarios

**Service fails immediately after a package update.** Capture the unit state, exit status and recent journal. Look for missing configuration files, changed paths or unsupported command-line flags. Compare `FragmentPath` and `DropInPaths` with the documented deployment, without modifying them during evidence collection.

**Service starts at boot but an API is unreachable.** First establish whether systemd reports active; then check application health, the listening socket and the dependency chain. A running process can still fail to bind a port or respond to requests. Avoid assuming a firewall problem merely because systemd says active.

**Service restarts every few seconds.** Inspect `NRestarts`, the last 25 journal entries and the exit status. Look for recurring failures such as permission errors, missing environment variables, exhausted storage or dependency timeouts. Before any change, preserve a time-stamped record and determine whether the service has a configured restart limit.

## Verification, pitfalls and operational conclusion

For a syntax check use `bash -n service-triage.sh`. For a smoke test, run it against a known installed service and confirm that it prints state, properties, journal and dependency information without changing `ActiveState` or `NRestarts`. Compare `systemctl show UNIT -p ActiveState -p NRestarts` before and after. Test a nonexistent service name to confirm graceful reporting; test `--help` as input to confirm validation rejects it.

Typical mistakes include treating `is-enabled` as a health check, overlooking user services (`systemctl --user`), misreading `After=` as `Requires=`, running a repair before collecting logs, and sharing unsanitized journal output. The practical rule is **observe, correlate, verify externally, then propose a reversible change**. Service restarts and configuration edits belong to a separate approved maintenance step with a rollback plan.
