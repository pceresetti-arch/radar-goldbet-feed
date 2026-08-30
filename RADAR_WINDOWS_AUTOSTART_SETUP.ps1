$ErrorActionPreference = 'Stop'

# Radar Windows autostart repair/setup.
# Run once from an elevated PowerShell window.

$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $IsAdmin) {
    throw 'Open PowerShell as Administrator and run this setup again.'
}

$Repo = 'https://raw.githubusercontent.com/pceresetti-arch/radar-goldbet-feed/main'
$RunnerTaskName = 'Radar GitHub Residential Runner'
$ImmediateRefreshTaskName = 'Radar BetFlag Immediate Refresh'

Write-Host '=== RADAR WINDOWS AUTOSTART SETUP ==='
Write-Host '[1/3] Installing/repairing BetFlag TRUE OPEN watcher autostart...'
$WatcherSetup = Invoke-RestMethod "$Repo/BETFLAG_OPEN_CLOSE_WATCHER_SETUP.ps1"
Invoke-Expression $WatcherSetup

Write-Host '[2/3] Checking GitHub Actions residential runner autostart...'

function Get-RadarRunnerServices {
    @(Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'actions.runner.*' })
}

$services = Get-RadarRunnerServices
$listener = Get-CimInstance Win32_Process -Filter "Name='Runner.Listener.exe'" -ErrorAction SilentlyContinue | Select-Object -First 1
$runnerRoot = $null
$CurrentUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name

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

    Unregister-ScheduledTask -TaskName $RunnerTaskName -Confirm:$false -ErrorAction SilentlyContinue
}
elseif ($runnerRoot) {
    $runCmd = Join-Path $runnerRoot 'run.cmd'
    if (-not (Test-Path $runCmd)) {
        Write-Warning "Runner detected at $runnerRoot but run.cmd was not found."
    }
    else {
        # This runner was registered interactively. Starting that existing
        # registration as SYSTEM can fail because the runner credentials and
        # Windows user context were created for the interactive account.
        # Therefore start it automatically at that user's logon, with no manual
        # command required, and keep a persistent local log for diagnostics.
        $Wrapper = Join-Path $runnerRoot 'radar-runner-autostart.ps1'
        $Log = Join-Path $runnerRoot 'radar-runner-autostart.log'
        $wrapperText = @"
`$ErrorActionPreference = 'Continue'
Set-Location '$runnerRoot'
Add-Content -Path '$Log' -Value ((Get-Date -Format o) + ' START user=' + [Security.Principal.WindowsIdentity]::GetCurrent().Name)
try {
    & '$runCmd' *>> '$Log'
    Add-Content -Path '$Log' -Value ((Get-Date -Format o) + ' EXIT code=' + `$LASTEXITCODE)
    exit ([int](`$LASTEXITCODE -as [int]))
}
catch {
    Add-Content -Path '$Log' -Value ((Get-Date -Format o) + ' ERROR ' + `$_.Exception.ToString())
    exit 1
}
"@
        Set-Content -Path $Wrapper -Value $wrapperText -Encoding UTF8

        $Action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $Wrapper + '"') -WorkingDirectory $runnerRoot
        $Trigger = New-ScheduledTaskTrigger -AtLogOn -User $CurrentUser
        $Principal = New-ScheduledTaskPrincipal -UserId $CurrentUser -LogonType Interactive -RunLevel Highest
        $Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

        try { Unregister-ScheduledTask -TaskName $RunnerTaskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}
        Register-ScheduledTask -TaskName $RunnerTaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description 'Starts the already-configured GitHub Actions BetFlag residential runner automatically when the configured Windows user logs on after startup.' | Out-Null

        if ($listener) {
            Write-Host "RUNNER AUTOSTART TASK: installed for $CurrentUser. Current runner remains active."
        }
        else {
            Start-ScheduledTask -TaskName $RunnerTaskName
            Start-Sleep -Seconds 5
            $listener = Get-CimInstance Win32_Process -Filter "Name='Runner.Listener.exe'" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($listener) {
                Write-Host "RUNNER AUTOSTART TASK: installed for $CurrentUser and Runner.Listener.exe is now running."
            }
            else {
                Write-Warning "Autostart task was started but Runner.Listener.exe is not running. Diagnostic log: $Log"
                if (Test-Path $Log) {
                    Write-Host '--- runner autostart log tail ---'
                    Get-Content $Log -Tail 30
                    Write-Host '--- end log ---'
                }
            }
        }
    }
}
else {
    Write-Warning 'No Actions Runner service, Runner.Listener.exe, or C:\actions-runner\run.cmd was found.'
}

Write-Host '[3/3] Installing immediate BetFlag refresh after logon...'
$ImmediateRefreshMode = 'FALLBACK_5_MIN'
if ($runnerRoot) {
    $ImmediateWrapper = Join-Path $runnerRoot 'radar-betflag-immediate-refresh.ps1'
    $ImmediateLog = Join-Path $runnerRoot 'radar-betflag-immediate-refresh.log'
    $immediateText = @"
`$ErrorActionPreference = 'Continue'
`$log = '$ImmediateLog'
function Write-RadarLog([string]`$Message) {
    Add-Content -Path `$log -Value ((Get-Date -Format o) + ' ' + `$Message)
}

Write-RadarLog 'START'
# Give Windows networking and the self-hosted runner a short head start.
Start-Sleep -Seconds 15
`$online = `$false
for (`$i = 0; `$i -lt 12; `$i++) {
    if (Get-Process -Name 'Runner.Listener' -ErrorAction SilentlyContinue) {
        `$online = `$true
        break
    }
    Start-Sleep -Seconds 5
}
if (-not `$online) {
    Write-RadarLog 'SKIP runner_listener_not_online fallback=schedule_5min'
    exit 0
}

`$gh = Get-Command gh.exe -ErrorAction SilentlyContinue
if (-not `$gh) {
    Write-RadarLog 'SKIP gh_not_installed fallback=schedule_5min'
    exit 0
}

& `$gh.Source auth status --hostname github.com *> `$null
if (`$LASTEXITCODE -ne 0) {
    Write-RadarLog 'SKIP gh_not_authenticated fallback=schedule_5min'
    exit 0
}

Write-RadarLog 'DISPATCH betflag-residential-feed.yml'
& `$gh.Source workflow run betflag-residential-feed.yml --repo pceresetti-arch/radar-goldbet-feed *>> `$log
if (`$LASTEXITCODE -eq 0) {
    Write-RadarLog 'DISPATCH_OK'
    exit 0
}
Write-RadarLog ('DISPATCH_FAILED code=' + `$LASTEXITCODE + ' fallback=schedule_5min')
exit 0
"@
    Set-Content -Path $ImmediateWrapper -Value $immediateText -Encoding UTF8

    $ImmediateAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $ImmediateWrapper + '"') -WorkingDirectory $runnerRoot
    $ImmediateTrigger = New-ScheduledTaskTrigger -AtLogOn -User $CurrentUser
    $ImmediatePrincipal = New-ScheduledTaskPrincipal -UserId $CurrentUser -LogonType Interactive -RunLevel Highest
    $ImmediateSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 3)

    try { Unregister-ScheduledTask -TaskName $ImmediateRefreshTaskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}
    Register-ScheduledTask -TaskName $ImmediateRefreshTaskName -Action $ImmediateAction -Trigger $ImmediateTrigger -Principal $ImmediatePrincipal -Settings $ImmediateSettings -Description 'After Windows logon, waits for the residential runner and immediately dispatches the BetFlag feed when GitHub CLI authentication is available. Otherwise the normal 5-minute schedule remains the fallback.' | Out-Null

    $ghNow = Get-Command gh.exe -ErrorAction SilentlyContinue
    if ($ghNow) {
        & $ghNow.Source auth status --hostname github.com *> $null
        if ($LASTEXITCODE -eq 0) {
            $ImmediateRefreshMode = 'IMMEDIATE_DISPATCH_READY'
            Write-Host 'IMMEDIATE REFRESH: GitHub CLI is authenticated; next login will dispatch BetFlag as soon as the runner is online.'
        }
        else {
            Write-Host 'IMMEDIATE REFRESH: task installed, but GitHub CLI is not authenticated. Normal 5-minute schedule remains the fallback.'
        }
    }
    else {
        Write-Host 'IMMEDIATE REFRESH: task installed, but gh.exe is not installed. Normal 5-minute schedule remains the fallback.'
    }
}
else {
    Write-Warning 'Immediate refresh task not installed because the runner root was not found.'
}

$watchTask = Get-ScheduledTask -TaskName 'BetFlag True Open Close Watcher' -ErrorAction SilentlyContinue
$runnerServices = Get-RadarRunnerServices
$runnerTask = Get-ScheduledTask -TaskName $RunnerTaskName -ErrorAction SilentlyContinue
$immediateTask = Get-ScheduledTask -TaskName $ImmediateRefreshTaskName -ErrorAction SilentlyContinue
$runnerProcess = Get-CimInstance Win32_Process -Filter "Name='Runner.Listener.exe'" -ErrorAction SilentlyContinue | Select-Object -First 1

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
    $principal = $runnerTask.Principal.UserId
    Write-Host "GITHUB RUNNER AUTOSTART: $($runnerTask.State) / logon trigger installed / account=$principal"
    if ($runnerProcess) {
        Write-Host "GITHUB RUNNER PROCESS: RUNNING / pid=$($runnerProcess.ProcessId)"
    } else {
        Write-Warning 'GITHUB RUNNER PROCESS: NOT RUNNING'
    }
} else {
    Write-Warning 'GitHub residential runner autostart is still not configured.'
}

if ($immediateTask) {
    Write-Host "BETFLAG LOGIN REFRESH: $($immediateTask.State) / mode=$ImmediateRefreshMode / fallback=5min"
} else {
    Write-Warning 'BetFlag immediate-login refresh task is not configured.'
}

Write-Host 'Setup finished. After Windows restart/login the configured components start without manual runner commands.'
