<#
.SYNOPSIS
Creates SHA-256 file inventories and compares two directory trees.

.EXAMPLE
.\File-IntegrityToolkit.ps1 -Mode Inventory -Root .\Package

.EXAMPLE
.\File-IntegrityToolkit.ps1 -Mode Compare -Reference .\Expected -Candidate .\Actual

.EXAMPLE
.\File-IntegrityToolkit.ps1 -Demo
#>
[CmdletBinding(DefaultParameterSetName='Run')]
param(
    [Parameter(ParameterSetName='Run',Mandatory=$true)]
    [ValidateSet('Inventory','Compare')]
    [string]$Mode,

    [Parameter(ParameterSetName='Run')][string]$Root,
    [Parameter(ParameterSetName='Run')][string]$Reference,
    [Parameter(ParameterSetName='Run')][string]$Candidate,
    [Parameter(ParameterSetName='Run')][string[]]$Include=@('*'),
    [Parameter(ParameterSetName='Run')][switch]$ShowUnchanged,

    [Parameter(ParameterSetName='Demo',Mandatory=$true)]
    [switch]$Demo
)

function Get-Inventory {
    param([string]$Path,[string[]]$Patterns=@('*'))

    $base=(Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path.TrimEnd('\')
    Get-ChildItem -LiteralPath $base -File -Recurse -ErrorAction Stop |
        Where-Object {
            $name=$_.Name
            @($Patterns | Where-Object { $name -like $_ }).Count -gt 0
        } |
        Sort-Object FullName |
        ForEach-Object {
            [pscustomobject]@{
                RelativePath=$_.FullName.Substring($base.Length).TrimStart('\')
                SizeBytes=$_.Length
                Sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            }
        }
}

function Compare-Trees {
    param([string]$Left,[string]$Right,[string[]]$Patterns=@('*'),[switch]$IncludeUnchanged)

    $a=@{}; foreach($x in @(Get-Inventory $Left $Patterns)){$a[$x.RelativePath]=$x}
    $b=@{}; foreach($x in @(Get-Inventory $Right $Patterns)){$b[$x.RelativePath]=$x}

    foreach($path in @($a.Keys+$b.Keys | Sort-Object -Unique)){
        if(-not $a.ContainsKey($path)){
            [pscustomobject]@{Status='EXTRA';Path=$path}
            continue
        }
        if(-not $b.ContainsKey($path)){
            [pscustomobject]@{Status='MISSING';Path=$path}
            continue
        }

        $same=$a[$path].SizeBytes -eq $b[$path].SizeBytes -and $a[$path].Sha256 -eq $b[$path].Sha256
        if(-not $same -or $IncludeUnchanged){
            [pscustomobject]@{Status=if($same){'UNCHANGED'}else{'CHANGED'};Path=$path}
        }
    }
}

if($Demo){
    $temp=Join-Path ([IO.Path]::GetTempPath()) ('file-integrity-demo-'+[guid]::NewGuid())
    $ref=Join-Path $temp 'reference'
    $cand=Join-Path $temp 'candidate'
    New-Item -ItemType Directory -Path $ref,$cand | Out-Null

    try {
        New-Item -ItemType Directory -Path (Join-Path $ref 'config'),(Join-Path $ref 'scripts'),(Join-Path $cand 'config'),(Join-Path $cand 'temp') | Out-Null
        Set-Content (Join-Path $ref 'config\app.json') '{"port":8080}' -NoNewline
        Set-Content (Join-Path $cand 'config\app.json') '{"port":9090}' -NoNewline
        Set-Content (Join-Path $ref 'scripts\start.ps1') 'Write-Output start' -NoNewline
        Set-Content (Join-Path $cand 'temp\debug.log') 'debug' -NoNewline

        Compare-Trees $ref $cand -IncludeUnchanged
    }
    finally {
        Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
    }
    return
}

if($Mode -eq 'Inventory'){
    if(-not $Root){throw '-Root is required for Inventory mode.'}
    Get-Inventory $Root $Include
    return
}

if(-not $Reference -or -not $Candidate){throw '-Reference and -Candidate are required for Compare mode.'}
Compare-Trees $Reference $Candidate $Include -IncludeUnchanged:$ShowUnchanged
