# systemd service failure diagnostics and verified recovery

## Purpose

On Linux servers using systemd, a service can fail because of an invalid executable path, missing service account, inaccessible working directory, dependency failure, startup timeout, exhausted disk or inodes, or a bug in the application. A process that is active is not necessarily serving requests. This practical LPIC-1 chapter provides a read-only triage path and a controlled lab exercise.

Use it for services that fail to start, restart repeatedly, or run without serving clients. Do not apply it to systems using OpenRC or SysV-only init, or to containers without systemd as PID 1. During an incident, preserve evidence before making changes. Never restart a critical production service merely to clear a red status.

## Establish the unit state

```bash
systemctl is-enabled ssh.service
systemctl is-active ssh.service
systemctl status ssh.service --no-pager --full
systemctl show ssh.service -p LoadState -p ActiveState -p SubState -p Result -p ExecMainStatus -p NRestarts
```

Replace ssh.service with the actual unit. Enabled means configured for automatic activation, not currently running. Static units may be started through dependencies. Masked units cannot be started normally. A successful oneshot service may exit and appear inactive: interpret its Result and exit status rather than assuming failure.

## Inspect the effective configuration and journal

```bash
systemctl cat ssh.service
systemctl show ssh.service -p FragmentPath -p DropInPaths -p ExecStart -p User -p WorkingDirectory
systemctl list-dependencies ssh.service --no-pager
journalctl -u ssh.service -b -n 100 --no-pager -o short-iso
journalctl -u ssh.service --since "30 minutes ago" --no-pager
```

The effective unit includes drop-ins, which may override a vendor-managed file. The current-boot flag excludes older boots. Persistent journaling is necessary to retain older records. Logs may contain secrets and personal information; redact them before sharing.

| Symptom | Likely direction | First check |
| --- | --- | --- |
| 203/EXEC | Missing executable or interpreter, permission problem | ExecStart path and executable mode |
| 200/CHDIR | Invalid or inaccessible WorkingDirectory | Parent-directory permissions |
| 217/USER | Missing service account | Account lookup |
| Start request repeated too quickly | Restart rate limit after prior errors | First failure before restart loop |
| Dependency failed | Required unit did not start | Dependent unit status and journal |
| Timeout | Readiness protocol or slow startup | Type, TimeoutStartSec, app logs |

A generic exit status 1 is not a diagnosis. Read the earliest application error in the incident window, not only the last systemd message.

## Check host-level constraints

```bash
df -h
df -i
free -h
uptime
ss -lntp
getent passwd www-data
namei -l /srv/example/current
systemctl --failed --no-pager
```

Disk space and inode exhaustion are separate conditions. A service user may read the final file but lack search permission on a parent directory. A listening port can be bound to loopback instead of the intended interface. Security enforcement denials require examining policy and audit logs; disabling SELinux or AppArmor is not an acceptable diagnostic shortcut.

For HTTP services, a documented health endpoint is stronger evidence than process state. A successful localhost request does not prove the endpoint is reachable through the reverse proxy or from client networks.

## A reproducible oneshot lab

On a disposable VM, create this unit. It checks a standard file without binding a port or writing persistent data:

```ini
# /etc/systemd/system/lpic-file-check.service
[Unit]
Description=LPIC-1 file readability demonstration

[Service]
Type=oneshot
ExecStart=/usr/bin/test -r /etc/hosts
User=nobody
```

Validate the unit, reload definitions, and run it in the lab:

```bash
sudo systemd-analyze verify /etc/systemd/system/lpic-file-check.service
sudo systemctl daemon-reload
sudo systemctl start lpic-file-check.service
systemctl show lpic-file-check.service -p Result -p ExecMainStatus
journalctl -u lpic-file-check.service -b -n 20 --no-pager
```

Expected behavior: the service succeeds, even though a completed oneshot unit may be inactive.

Concrete expected output for the successful lab run (`systemctl show lpic-file-check.service -p Result -p ExecMainStatus`):

```text
Result=success
ExecMainStatus=0
```

The command exits with code 0. Journal timestamps, PIDs, and ancillary messages vary by machine and are intentionally not presented as exact fixed output. To reproduce failure safely, change the checked path to a nonexistent lab-only path, reload definitions, start again, and inspect the nonzero result. Restore the original path and verify success. daemon-reload updates unit definitions; it does not restart a running process.

## Three operational scenarios

**After deployment:** 203/EXEC may indicate an incorrect binary path, missing interpreter, or permissions. Inspect the deployment tree and unit command before touching the restart policy. A restart loop may obscure the original deployment error.

**Active but unavailable:** Inspect listening sockets, bind address, reverse proxy, firewall, and application dependencies. An active process with an unhealthy endpoint is not a recovered service.

**Works manually, fails at boot:** Inspect mount readiness, network-online dependencies, and ordering. After= defines ordering but does not automatically establish a dependency. Avoid adding arbitrary sleeps in place of understanding readiness.

## Change control and verification

A production fix requires an approved maintenance window where relevant, a backup of affected configuration, a narrow change, and a rollback path. Prefer systemd drop-ins to editing vendor unit files. Validate syntax before any controlled restart. Do not use reset-failed to disguise an unresolved fault; it clears recorded failed state and counters, not the root cause.

After remediation, compare pre- and post-change journal evidence, exit status, restart counter, listening socket, application health endpoint, and dependent services. Observe for a meaningful period because scheduled work may trigger delayed failures. If health worsens, restore the backed-up configuration and perform an approved rollback.

## Practical takeaway

Read the effective unit, find the first meaningful error, correlate host resources and application behavior, and separate observation from remediation. For LPIC-1, understand start, stop, restart, reload, daemon-reload, enable, disable, mask, and reset-failed. A successful endpoint check and post-change recheck are the real completion criteria.