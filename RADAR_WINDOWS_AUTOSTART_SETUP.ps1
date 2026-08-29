$ErrorActionPreference = 'Stop'

# Radar Windows autostart repair/setup.
# Run once from an elevated PowerShell window.

$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $IsAdmin) {
    throw 'Open PowerShell as Administrator and run this setup again.'
}

$Repo = 'https://raw.githubusercontent.com/pceresetti-arch/radar-goldbet-feed/main'
$RunnerTaskName = 'Radar GitHub Residential Runner'

Write-Host '=== RADAR WINDOWS AUTOSTART SETUP ==='
Write-Host '[1/2] Installing/repairing BetFlag TRUE OPEN watcher autostart...'
$WatcherSetup = Invoke-RestMethod "$Repo/BETFLAG_OPEN_CLOSE_WATCHER_SETUP.ps1"
Invoke-Expression $WatcherSetup

Write-Host '[2/2] Checking GitHub Actions residential runner autostart...'

function Get-RadarRunnerServices {
    @(Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'actions.runner.*' })
}

$services = Get-RadarRunnerServices
$listener = Get-CimInstance Win32_Process -Filter "Name='Runner.Listener.exe'" -ErrorAction SilentlyContinue | Select-Object -First 1
$runnerRoot = $null

if ($listener -and $listener.ExecutablePath) {
    $binDir = Split-Path -Parent $listener.ExecutablePath
    $runnerRoot = Split-Path -Parent $binDir
    Write-Host "Runner root detected: $runnerRoot"
}
elseif (Test-Path 'C:\actions-runner\run.cmd') {
    $runnerRoot = 'C:\actions-runner'
    Write-Host "Runner root detected from configured path: $runnerRoot"
}

if ($services.Count -gt 0) {
    foreach ($service in $services) {
        Set-Service -Name $service.Name -StartupType Automatic
        Write-Host "RUNNER SERVICE: $($service.Name) -> Automatic"
    }

    if (-not $listener) {
        foreach ($service in $services) {
            if ($service.Status -ne 'Running') {
                Start-Service -Name $service.Name
            }
        }
    }
    else {
        Write-Host 'Manual Runner.Listener.exe is currently active; leaving it untouched. The Windows service is configured for the next boot.'
    }

    # Remove the fallback task if a real Actions Runner Windows service exists.
    Unregister-ScheduledTask -TaskName $RunnerTaskName -Confirm:$false -ErrorAction SilentlyContinue
}
elseif ($runnerRoot) {
    $runCmd = Join-Path $runnerRoot 'run.cmd'
    if (-not (Test-Path $runCmd)) {
        Write-Warning "Runner detected at $runnerRoot but run.cmd was not found."
    }
    else {
        # Windows runners that were initially configured interactively do not
        # expose svc.cmd. GitHub's supported service conversion requires
        # removing/re-registering the runner. To avoid disturbing the already
        # working registration, use a SYSTEM startup task as a safe autostart
        # fallback. C:\actions-runner is intentionally system-account accessible.
        $Action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/c ""' + $runCmd + '""') -WorkingDirectory $runnerRoot
        $Trigger = New-ScheduledTaskTrigger -AtStartup
        $Principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
        $Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

        try { Unregister-ScheduledTask -TaskName $RunnerTaskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}
        Register-ScheduledTask -TaskName $RunnerTaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description 'Starts the already-configured GitHub Actions BetFlag residential runner automatically at Windows startup.' | Out-Null

        if ($listener) {
            Write-Host 'RUNNER AUTOSTART TASK: installed. Current manual runner remains active; the task will take over automatically after the next reboot.'
        }
        else {
            Start-ScheduledTask -TaskName $RunnerTaskName
            Start-Sleep -Seconds 3
            Write-Host 'RUNNER AUTOSTART TASK: installed and started.'
        }
    }
}
else {
    Write-Warning 'No Actions Runner service, Runner.Listener.exe, or C:\actions-runner\run.cmd was found.'
}

$watchTask = Get-ScheduledTask -TaskName 'BetFlag True Open Close Watcher' -ErrorAction SilentlyContinue
$runnerServices = Get-RadarRunnerServices
$runnerTask = Get-ScheduledTask -TaskName $RunnerTaskName -ErrorAction SilentlyContinue

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
        Write-Host "GITHUB RUNNER SERVICE: $($service.Name) / state=$($fresh.State) / start=$($fresh.StartMode)"
    }
}
elseif ($runnerTask) {
    Write-Host "GITHUB RUNNER AUTOSTART: $($runnerTask.State) / startup trigger installed / account=SYSTEM"
} else {
    Write-Warning 'GitHub residential runner autostart is still not configured.'
}

Write-Host 'Setup finished. After the next reboot the configured components start without manual runner commands.'
