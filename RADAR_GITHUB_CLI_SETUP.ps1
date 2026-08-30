$ErrorActionPreference = 'Stop'

$TaskName = 'Radar BetFlag Immediate Refresh'
$Repo = 'pceresetti-arch/radar-goldbet-feed'
$Workflow = 'betflag-residential-feed.yml'

$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $IsAdmin) {
    throw 'Open PowerShell as Administrator and run this setup again.'
}

function Resolve-Gh {
    $cmd = Get-Command gh.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $candidates = @(
        "$env:ProgramFiles\GitHub CLI\gh.exe",
        "$env:LOCALAPPDATA\Programs\GitHub CLI\gh.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) { return $candidate }
    }
    return $null
}

function Test-GhAuth([string]$GhPath) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $GhPath
    $psi.Arguments = 'auth status --hostname github.com'
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $p = [System.Diagnostics.Process]::Start($psi)
    $p.WaitForExit()
    return ($p.ExitCode -eq 0)
}

Write-Host '=== RADAR GITHUB CLI SETUP ==='
$gh = Resolve-Gh

if (-not $gh) {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw 'GitHub CLI is missing and winget.exe is not available. Install GitHub CLI, then run this setup again.'
    }

    Write-Host 'Installing GitHub CLI with winget...'
    & $winget.Source install --id GitHub.cli -e --source winget --accept-source-agreements --accept-package-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        throw "winget could not install GitHub CLI (exit code $LASTEXITCODE)."
    }

    Start-Sleep -Seconds 3
    $gh = Resolve-Gh
    if (-not $gh) {
        throw 'GitHub CLI installation completed but gh.exe could not be located.'
    }
}

Write-Host "GH: $gh"

if (-not (Test-GhAuth $gh)) {
    Write-Host 'GitHub authentication is required once. A browser/device login will open now.'
    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $gh auth login --hostname github.com --git-protocol https --web
    $loginCode = $LASTEXITCODE
    $ErrorActionPreference = $oldEap
    if ($loginCode -ne 0) {
        throw 'GitHub CLI authentication did not complete successfully.'
    }
}

if (-not (Test-GhAuth $gh)) {
    throw 'GitHub CLI is installed but still not authenticated.'
}

Write-Host 'GH AUTH: OK'

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    Write-Host "Immediate refresh task found: $TaskName"
    try {
        Start-ScheduledTask -TaskName $TaskName
        Write-Host 'Immediate refresh task started for validation.'
    }
    catch {
        Write-Warning "Could not start the immediate refresh task now: $($_.Exception.Message)"
    }
}
else {
    Write-Warning "Task '$TaskName' was not found. Re-run RADAR_WINDOWS_AUTOSTART_SETUP.ps1 after this setup."
}

Write-Host ''
Write-Host '=== RESULT ==='
Write-Host 'GITHUB CLI: INSTALLED'
Write-Host 'GITHUB AUTH: READY'
Write-Host 'BETFLAG LOGIN REFRESH: IMMEDIATE_DISPATCH_READY'
Write-Host 'The normal 5-minute workflow schedule remains as fallback.'
