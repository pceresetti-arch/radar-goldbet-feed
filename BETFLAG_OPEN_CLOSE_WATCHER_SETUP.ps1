$ErrorActionPreference = 'Stop'
$Repo = 'https://raw.githubusercontent.com/pceresetti-arch/radar-goldbet-feed/main'
$Root = 'C:\BetFlagRadar'
$State = Join-Path $Root 'state'
$Script = Join-Path $Root 'betflag_true_open_close_watcher.py'
New-Item -ItemType Directory -Force -Path $Root,$State | Out-Null
Invoke-WebRequest -UseBasicParsing "$Repo/collector/betflag_true_open_close_watcher.py" -OutFile $Script
$Python = (Get-Command python.exe -ErrorAction Stop).Source
$TaskName = 'BetFlag True Open Close Watcher'
$Action = New-ScheduledTaskAction -Execute $Python -Argument ('"' + $Script + '" --window-seconds 50 --interval 20')
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
try { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -RunLevel Highest -Description 'Poll BetFlag every ~20s through the residential PC to capture market birth/open, movement and final pre-kickoff close.' | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "INSTALLED: $TaskName"
Write-Host "STATE: $State\betflag-open-close-watch.json"
Write-Host "PYTHON: $Python"
