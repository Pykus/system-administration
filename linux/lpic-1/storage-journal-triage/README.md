# LPIC-1 storage and journal triage

This example turns a few common Linux commands into a repeatable read-only triage workflow for the case where a service stops writing data, logs begin failing, or the machine reports storage pressure.

## What the script checks

`triage.sh` collects five independent signals:

1. filesystem capacity with `df -hP`;
2. inode exhaustion with `df -iP`;
3. failed systemd units;
4. warning-to-alert journal entries from a chosen time window;
5. top-level disk usage under a chosen path such as `/var`.

These checks answer different questions. A filesystem can have free gigabytes but no free inodes, or a service can fail while storage is healthy.

## Usage

```bash
chmod +x triage.sh
./triage.sh
./triage.sh --since "2 hours ago" --path /var
```

The script does not delete files, vacuum journals, restart units, remount filesystems, or modify permissions.

## Reading the output

- `Use% = 100%` in the filesystem section points to capacity pressure.
- `IUse% = 100%` with free disk space points to inode exhaustion, often caused by very large numbers of small files.
- failed units show the immediate service symptom, not necessarily the root cause.
- journal warnings narrow the incident to a time window before any cleanup is attempted.
- unexpectedly large directories under `/var` help identify where storage is accumulating.

Use the evidence to decide what to inspect next; do not start by deleting logs.
