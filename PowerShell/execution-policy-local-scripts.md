# PowerShell local scripts: fixing `Restricted` safely

When a workstation refuses to run trusted local `.ps1` files because the effective execution policy is `Restricted`, prefer a scoped policy change instead of launching every command with `-ExecutionPolicy Bypass`.

## 1. Inspect the effective policy

```powershell
Get-ExecutionPolicy
Get-ExecutionPolicy -List
```

If `MachinePolicy` or `UserPolicy` is defined, Group Policy may override local settings. Do not fight a domain policy from the workstation.

## 2. Set a user-scoped policy

For a workstation where the user is allowed to run reviewed local scripts:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
```

This changes only the current user's preference. It does not weaken `LocalMachine` for every user.

## 3. Unblock reviewed local scripts

Files copied from another computer or downloaded from the Internet may carry a Mark-of-the-Web stream. After reviewing the scripts, unblock only the intended directory:

```powershell
Get-ChildItem "C:\Automation" -Filter "*.ps1" -File |
    Unblock-File
```

Avoid recursively unblocking large directories you have not reviewed.

## 4. Verify

Open a fresh PowerShell process and run:

```powershell
Get-ExecutionPolicy
& "C:\Automation\Test-Script.ps1"
```

Expected result: the effective policy is `RemoteSigned` and the trusted local script starts without requiring `-ExecutionPolicy Bypass`.

## Rollback

To remove the user-level preference and fall back to higher-precedence scopes:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy Undefined -Force
```

Then verify again with:

```powershell
Get-ExecutionPolicy -List
```

## Notes

- `ExecutionPolicy` is a safety feature, not a security boundary.
- Do not permanently use `Unrestricted` or `Bypass` just to make automation work.
- If a domain GPO defines the policy, correct the GPO or obtain the intended exception instead of overriding it locally.
- Unblock only scripts whose source and contents you have reviewed.
