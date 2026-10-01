# Wazuh Active Response: domain-wide GPUpdate and GPUpdate + reboot

This runbook deploys two **Windows Wazuh Active Response scripts** to domain-joined endpoints through a **Computer Startup GPO**:

- `gpupdate-computer.cmd` — runs `gpupdate /target:computer /force`
- `gpupdate-computer-reboot.cmd` — runs the same update and reboots only when GPUpdate returns exit code 0

The example is intentionally generic. Replace `example.local`, the OU DN, API URL and agent IDs with values from your environment.

## Why deploy the scripts with GPO?

The Wazuh manager/API can dispatch an Active Response request, but the executable must exist on the target endpoint. On Windows, custom Active Response executables/scripts live in:

```text
C:\Program Files (x86)\ossec-agent\active-response\bin
```

Some installations use:

```text
C:\Program Files\ossec-agent\active-response\bin
```

The deployment script checks both locations.

A key operational lesson: **HTTP 200 / "AR command was sent" means the manager accepted and dispatched the request. It does not prove the endpoint executed the script.** Always verify endpoint-side evidence.

Official Wazuh references:

- https://documentation.wazuh.com/current/user-manual/capabilities/active-response/how-to-configure.html
- https://documentation.wazuh.com/current/user-manual/capabilities/active-response/custom-active-response-scripts.html
- https://documentation.wazuh.com/current/user-manual/api/reference.html

## Files

```text
.
├── README.md
├── manager/
│   └── ossec-command-block.xml
├── examples/
│   └── Send-WazuhActiveResponse.ps1
└── scripts/
    ├── New-WazuhActiveResponseGpo.ps1
    └── Test-WazuhActiveResponseClient.ps1
```

The GPO creation script generates the two CMD payload files and the startup deployment wrapper inside the GPO's SYSVOL folder.

## 1. Prerequisites

You need:

- Active Directory domain services
- Group Policy Management / the PowerShell `GroupPolicy` module on the machine used to create the GPO
- Wazuh agents installed on Windows endpoints
- administrator rights to create and link a GPO
- administrator rights on the Wazuh manager if you choose named-command mode
- a Wazuh API token if you want to dispatch the action through the API

Run the GPO script from a domain controller or an administrative workstation with GPMC/RSAT.

## 2. Create and link the deployment GPO

Copy `scripts/New-WazuhActiveResponseGpo.ps1` to the administrative machine.

Example:

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force

.\New-WazuhActiveResponseGpo.ps1 `
  -DomainDns "example.local" `
  -TargetOuDn "OU=Computers,DC=example,DC=local" `
  -GpoName "Wazuh - Active Response"
```

The script:

1. validates the domain and target OU;
2. creates or updates the GPO;
3. generates both Active Response CMD files;
4. generates a startup deployment script;
5. registers the startup script in the GPO;
6. links the GPO to the selected computer OU;
7. increments the computer-side GPO version;
8. verifies that all required files exist in SYSVOL.

It does **not** put organization-specific hostnames, credentials, IP addresses or secrets in the GPO.

## 3. First rollout to clients

The deployment itself runs as a **Computer Startup Script**, therefore an existing endpoint normally needs one ordinary reboot before it receives the Active Response files.

On a test client, run as administrator:

```cmd
gpupdate /force
shutdown /r /t 0
```

After startup, verify:

```powershell
.\Test-WazuhActiveResponseClient.ps1
```

Or inspect manually:

```powershell
Get-Service WazuhSvc
Get-Content "C:\ProgramData\WazuhAR\Logs\ActiveResponseDeploy.log" -Tail 50
```

Expected evidence includes lines similar to:

```text
DEPLOYED gpupdate-computer.cmd
DEPLOYED gpupdate-computer-reboot.cmd
WazuhSvc restarted
SUCCESS
```

Also verify the files exist under the endpoint's `active-response\bin` directory.

## 4. Optional manager command definitions

For API calls beginning with `!`, Wazuh treats the value as a **script name** rather than a configured command name. This is the simplest way to dispatch these exact payload files manually.

You can also define named commands on the manager. A sample is provided in:

```text
manager/ossec-command-block.xml
```

Merge the relevant `<command>` blocks inside the manager's existing `<ossec_config>` in:

```text
/var/ossec/etc/ossec.conf
```

Then validate and restart the manager using the procedures appropriate for your Wazuh version/environment.

Typical service restart:

```bash
sudo systemctl restart wazuh-manager
```

## 5. Dispatch Active Response through the Wazuh API

The API endpoint is:

```text
PUT /active-response
```

Wazuh documents that when `command` begins with `!`, the value refers to a script name instead of a configured command name.

Example:

```powershell
.\examples\Send-WazuhActiveResponse.ps1 `
  -ApiBase "https://wazuh.example.local:55000" `
  -Token "<JWT>" `
  -AgentId "001" `
  -Action GpUpdate
```

For GPUpdate + reboot:

```powershell
.\examples\Send-WazuhActiveResponse.ps1 `
  -ApiBase "https://wazuh.example.local:55000" `
  -Token "<JWT>" `
  -AgentId "001" `
  -Action GpUpdateAndReboot
```

## 6. What counts as success?

Do **not** treat this response alone as execution success:

```json
{
  "message": "AR command was sent to all agents",
  "error": 0
}
```

It proves dispatch, not endpoint execution.

For `GpUpdate`, confirm the endpoint log:

```text
C:\ProgramData\WazuhAR\Logs\gpupdate-computer.log
```

For `GpUpdateAndReboot`, confirm:

1. the endpoint log contains `GPUPDATE RC=0`;
2. the log contains `Scheduling reboot`;
3. the endpoint actually disconnects/reboots and returns;
4. the Wazuh agent becomes active again after boot.

This distinction is important for dashboards and automation: report states such as:

```text
dispatched -> endpoint-confirmed -> reboot-observed -> agent-returned
```

rather than changing directly from `dispatched` to `success`.

## 7. Troubleshooting

### API returns "command was sent", but nothing happens

Check the endpoint first:

```powershell
.\Test-WazuhActiveResponseClient.ps1
```

The most common causes are:

- the CMD payload was never deployed to `active-response\bin`;
- the endpoint has not rebooted since the startup GPO was applied;
- `WazuhSvc` was not restarted after a changed payload;
- `gpupdate.exe` returned a non-zero exit code;
- the reboot script intentionally skipped reboot because GPUpdate failed.

### GPUpdate runs, but reboot does not

Read:

```text
C:\ProgramData\WazuhAR\Logs\gpupdate-computer-reboot.log
```

The supplied payload only schedules reboot when `gpupdate.exe` exits with code 0.

### Client did not receive the startup deployment

Verify:

```cmd
gpresult /scope computer /r
```

and check that the GPO is in the computer's Resultant Set of Policy.

Then inspect:

```text
C:\ProgramData\WazuhAR\Logs\ActiveResponseDeploy.log
```

### Wazuh agent is offline

Do not use Active Response as the recovery transport for an agent that cannot communicate with the manager. Use another administrative path to restore connectivity first.

## 8. Security notes

- Scope the GPO only to intended computer OUs.
- Do not embed API credentials or JWTs in SYSVOL.
- Use least-privilege RBAC for the Wazuh API account.
- Test on a small OU before domain-wide deployment.
- `gpupdate-computer-reboot.cmd` uses a forced reboot and can close applications with unsaved work.
- Keep endpoint logs so an automation system can distinguish **dispatch** from **execution**.
