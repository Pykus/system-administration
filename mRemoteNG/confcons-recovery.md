# mRemoteNG `confCons.xml` recovery drill

## Scenario

mRemoteNG suddenly starts asking for a configuration/master password even though the operator did not intentionally enable one, and the connection tree fails to load.

A plausible trigger is an interrupted or incomplete write of `confCons.xml` — for example after sleep/resume, a crash, forced shutdown, storage interruption, or another abrupt process termination. This is only a working hypothesis: a password prompt can also be legitimate if a Master Password was previously configured.

Typical symptoms:

- unexpected password prompt on startup,
- error while loading `confCons.xml`,
- missing or empty connection tree,
- exception in the mRemoteNG log,
- several timestamped `.backup` files next to the active configuration.

## Rule zero

Do **not** guess or enter Windows/domain/admin passwords into the mRemoteNG Master Password prompt.

Do **not** delete the active configuration before making a copy.

## Default location

Use environment variables instead of hard-coded user names:

```text
%APPDATA%\mRemoteNG
```

The active connection file is normally:

```text
%APPDATA%\mRemoteNG\confCons.xml
```

## Recovery procedure

### 1. Close mRemoteNG

```cmd
taskkill /IM mRemoteNG.exe /F
```

### 2. Make a full safety copy

```cmd
mkdir "%USERPROFILE%\Desktop\mRemoteNG-RECOVERY"
xcopy "%APPDATA%\mRemoteNG" "%USERPROFILE%\Desktop\mRemoteNG-RECOVERY\" /E /I /H /K /Y
```

Do not continue until the copy exists.

### 3. List configuration files and backups newest-first

```cmd
powershell -NoProfile -Command "Get-ChildItem $env:APPDATA\mRemoteNG -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object LastWriteTime,Length,FullName"
```

Look for files such as:

```text
confCons.xml
confCons.xml.<timestamp>.backup
confCons.xml.bak
```

Choose the newest backup from **before the incident**. If several backups created at the failure time have exactly the same size as the active file, prefer an older pre-incident backup.

### 4. Validate the candidate backup as XML

Replace `<BACKUP_FILE>` with the selected backup file name:

```cmd
powershell -NoProfile -Command "try { [xml](Get-Content -Raw '$env:APPDATA\mRemoteNG\<BACKUP_FILE>') | Out-Null; 'BACKUP XML OK' } catch { 'BACKUP XML ERROR: ' + $_.Exception.Message }"
```

Continue only if the result is:

```text
BACKUP XML OK
```

### 5. Preserve the current file and restore the backup

```cmd
taskkill /IM mRemoteNG.exe /F
ren "%APPDATA%\mRemoteNG\confCons.xml" confCons.xml.BAD
copy /Y "%APPDATA%\mRemoteNG\<BACKUP_FILE>" "%APPDATA%\mRemoteNG\confCons.xml"
```

Never overwrite the damaged/suspect file without retaining it.

### 6. Start mRemoteNG and verify

Confirm that:

- the unexpected password prompt is gone,
- the connection tree loads,
- representative RDP/SSH/VNC entries are present,
- inherited credentials/settings still look correct,
- no new load error is written to `mRemoteNG.log`.

If the prompt remains, restore the safety copy and investigate whether a real Master Password was configured or whether the backup is also affected.

## Fast interpretation

- **Backup restores normal startup:** active `confCons.xml` was probably corrupted or otherwise inconsistent.
- **Backup still asks for password:** do not assume corruption; check whether Master Password protection was intentionally enabled.
- **XML validation fails:** choose an earlier backup.
- **No backups exist:** preserve the active file, inspect logs, and recover from external backups/profile backups if available.

## Prevention

- Keep mRemoteNG's automatic timestamped backups enabled.
- Back up `%APPDATA%\mRemoteNG` as part of workstation profile protection.
- Avoid killing the application during configuration saves.
- After an abnormal sleep/resume or forced shutdown, close and reopen mRemoteNG before making many configuration changes.
- Never publish real connection files: they may contain host names, user names, domains, paths, and encrypted credential material.

## Anonymization note

This drill intentionally contains no real host names, user names, domains, IP addresses, passwords, or organization-specific paths. Examples use only environment variables and placeholders.
