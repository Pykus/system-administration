# Zabbix API access for a local administration dashboard

This note describes a manual setup for connecting a local administration dashboard to Zabbix with write access, while keeping credentials out of source control.

## 1. Create a dedicated API role

In **Users -> User roles**, create a role such as:

- **Name:** `Monitoring Dashboard Administrator`
- **User type:** `Admin`
- **API access:** enabled
- **API methods:** allow the methods required by the dashboard

Use `Super admin` only when the integration must change Zabbix-wide administration settings that are unavailable to an `Admin` role.

## 2. Create a dedicated user group

Create a group such as:

`Monitoring Dashboard API`

Grant **Read-write** access to the host groups and template groups the integration is expected to manage.

Avoid using a personal administrator account for API access.

## 3. Create the service account

Create a dedicated account such as:

`monitoring-api`

Assign it to:

- the `Monitoring Dashboard API` group,
- the `Monitoring Dashboard Administrator` role.

The account should be used only by the integration.

## 4. Generate an API token

Open **Users -> API tokens** and create a token for the service account.

Example metadata:

- **Name:** `Local dashboard`
- **User:** `monitoring-api`
- **Enabled:** yes
- **Expiration:** set according to the local credential-rotation policy

Copy the token when Zabbix displays it. Do not place it in scripts, documentation, screenshots, issue trackers, or Git commits.

## 5. Store the token locally on Windows

Create a local directory outside source-controlled content, for example:

```powershell
New-Item -ItemType Directory -Force C:\MonitoringDashboard\secrets
notepad C:\MonitoringDashboard\secrets\zabbix.env
```

Example file contents:

```text
ZABBIX_API_URL=https://monitoring.example.local/zabbix/api_jsonrpc.php
ZABBIX_API_TOKEN=<API_TOKEN>
```

Replace the example URL and placeholder locally. Never commit the real values.

## 6. Restrict NTFS permissions

Run PowerShell **as Administrator**.

First verify elevation:

```powershell
([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
```

The result should be `True`.

If the directory belongs to another account, take ownership first:

```powershell
takeown /F "C:\MonitoringDashboard\secrets" /A
takeown /F "C:\MonitoringDashboard\secrets\zabbix.env" /A
```

Then limit access. Using well-known SIDs avoids problems on non-English Windows installations:

```powershell
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$path = "C:\MonitoringDashboard\secrets"

icacls $path /inheritance:r

icacls $path /grant:r `
    "$($user):(OI)(CI)F" `
    "*S-1-5-18:(OI)(CI)F" `
    "*S-1-5-32-544:(OI)(CI)F"

icacls "$path\zabbix.env" /inheritance:r

icacls "$path\zabbix.env" /grant:r `
    "$($user):F" `
    "*S-1-5-18:F" `
    "*S-1-5-32-544:F"
```

The SIDs used above are:

- `S-1-5-18` — Local System,
- `S-1-5-32-544` — local Administrators group.

Verify the result:

```powershell
(Get-Acl "C:\MonitoringDashboard\secrets").Owner
icacls "C:\MonitoringDashboard\secrets"
icacls "C:\MonitoringDashboard\secrets\zabbix.env"
```

## 7. Keep secrets out of Git

Add these rules to the repository's `.gitignore`:

```gitignore
secrets/
*.env
.env
```

Before committing anything, verify that the secret file is ignored:

```powershell
git status --ignored
```

If a secret file was already added to the Git index, remove it from the index without deleting the local copy:

```powershell
git rm --cached -r secrets
```

If a real API token was ever committed, revoke it in Zabbix and create a new one. Removing the file from the latest commit does not remove the credential from Git history.

## 8. Recommended validation

Before enabling write operations in the dashboard:

1. confirm the API endpoint is reachable,
2. verify the token can read hosts and current problems,
3. test a harmless write operation on a non-production test host,
4. confirm the service account cannot access resources outside its intended scope,
5. record the token owner and rotation date.

Keep the API account separate from interactive administrator accounts and grant only the permissions the integration actually needs.
