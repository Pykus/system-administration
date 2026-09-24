[CmdletBinding()]
param(
    [string]$OutputDirectory = ".\environment-locks",
    [string]$PythonExecutable = "python",
    [string[]]$WingetPackageIds = @("Git.Git", "Python.Python.3.12", "Microsoft.VisualStudioCode"),
    [switch]$SkipPython,
    [switch]$SkipWinget
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

# Python: use the native package-lock mechanism directly.
if (-not $SkipPython) {
    try {
        & $PythonExecutable -m pip freeze |
            Set-Content (Join-Path $OutputDirectory "requirements.lock.txt") -Encoding UTF8
        Write-Host "Python packages saved."
    }
    catch { Write-Warning "Python export skipped: $($_.Exception.Message)" }
}

# WinGet: export to a temporary file, then keep only explicitly selected packages.
if (-not $SkipWinget) {
    $temp = Join-Path $env:TEMP ("winget-{0}.json" -f [guid]::NewGuid().ToString("N"))
    try {
        winget export --output $temp --include-versions --accept-source-agreements | Out-Null
        $data = Get-Content $temp -Raw | ConvertFrom-Json

        foreach ($source in @($data.Sources)) {
            $source.Packages = @($source.Packages | Where-Object {
                $WingetPackageIds -contains [string]$_.PackageIdentifier
            })
        }
        $data.Sources = @($data.Sources | Where-Object { @($_.Packages).Count -gt 0 })

        $data | ConvertTo-Json -Depth 10 |
            Set-Content (Join-Path $OutputDirectory "winget-packages.lock.json") -Encoding UTF8
        Write-Host "Selected WinGet packages saved."
    }
    catch { Write-Warning "WinGet export skipped: $($_.Exception.Message)" }
    finally { Remove-Item $temp -Force -ErrorAction SilentlyContinue }
}

Write-Host "Snapshot written to: $OutputDirectory"
