$ErrorActionPreference = 'Stop'

# Radar Windows autostart repair/setup.
# Run once from an elevated PowerShell window.

$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $IsAdmin) {
    throw 'Open PowerShell as Administrator and run this setup again.'
}

$Repo = 'https://raw.githubusercontent.com/pceresetti-arch/radar-goldbet-feed/main'

Write-Host '=== RADAR WINDOWS AUTOSTART SETUP ==='
Write-Host '[1/2] Installing/reparing BetFlag TRUE OPEN watcher autostart...'
$WatcherSetup = Invoke-RestMethod "$Repo/BETFLAG_OPEN_CLOSE_WATCHER_SETUP.ps1"
Invoke-Expression $WatcherSetup

Write-Host '[2/2] Checking GitHub Actions residential runner service...'

function Get-RadarRunnerServices {
    @(Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'actions.runner.*' })
}

$services = Get-RadarRunnerServices
$listener = Get-CimInstance Win32_Process -Filter "Name='Runner.Listener.exe'" -ErrorAction SilentlyContinue | Select-Object -First 1

if ($services.Count -eq 0) {
    if (-not $listener -or -not $listener.ExecutablePath) {
        Write-Warning 'No GitHub Actions runner service and no currently running Runner.Listener.exe were found. Start the residential runner manually once, then rerun this setup so its installation folder can be detected automatically.'
    }
    else {
        $binDir = Split-Path -Parent $listener.ExecutablePath
        $runnerRoot = Split-Path -Parent $binDir
        $svc = Join-Path $runnerRoot 'svc.cmd'
        if (-not (Test-Path $svc)) {
            Write-Warning "Runner detected at $runnerRoot but svc.cmd was not found. The watcher autostart is installed; the GitHub runner service still needs repair."
        }
        else {
            Write-Host "Runner root detected: $runnerRoot"
            Write-Host 'Installing GitHub Actions runner as a Windows service...'
            & $svc install
            if ($LASTEXITCODE -ne 0) {
                throw "svc.cmd install failed with exit code $LASTEXITCODE"
            }
            $services = Get-RadarRunnerServices
        }
    }
}

if ($services.Count -gt 0) {
    foreach ($service in $services) {
        Set-Service -Name $service.Name -StartupType Automatic
        Write-Host "RUNNER SERVICE: $($service.Name) -> Automatic"
    }

    # If the runner is currently being run interactively, do not start a second
    # listener for the same registered runner.  The Windows service will take
    # over automatically on the next reboot.  If no manual listener is active,
    # start the service now as well.
    if (-not $listener) {
        foreach ($service in $services) {
            if ($service.Status -ne 'Running') {
                Start-Service -Name $service.Name
            }
        }
    }
    else {
        Write-Host 'Manual Runner.Listener.exe is currently active; leaving it untouched. The service is installed/configured for the next Windows boot.'
    }
}

$watchTask = Get-ScheduledTask -TaskName 'BetFlag True Open Close Watcher' -ErrorAction SilentlyContinue
$runnerServices = Get-RadarRunnerServices

Write-Host ''
Write-Host '=== RESULT ==='
if ($watchTask) {
    Write-Host "TRUE OPEN WATCHER: $($watchTask.State) / startup trigger installed"
} else {
    Write-Warning 'TRUE OPEN watcher scheduled task was not found.'
}
if ($runnerServices.Count -gt 0) {
    foreach ($service in $runnerServices) {
        $fresh = Get-CimInstance Win32_Service -Filter "Name='$($service.Name)'"
        Write-Host "GITHUB RUNNER: $($service.Name) / state=$($fresh.State) / start=$($fresh.StartMode)"
    }
} else {
    Write-Warning 'GitHub residential runner is still not installed as a Windows service.'
}

Write-Host 'Setup finished. After the next reboot the configured components should start without manual commands.'
