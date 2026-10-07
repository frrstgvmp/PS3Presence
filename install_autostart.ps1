param(
    [bool]$StartNow = $true,
    [switch]$NoStart,
    [string]$ExecutablePath
)

$ErrorActionPreference = 'Stop'

$taskName = 'PS3 Discord Presence'
$projectDirectory = $PSScriptRoot
$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if ($ExecutablePath) {
    if (-not (Test-Path -LiteralPath $ExecutablePath -PathType Leaf)) { throw 'Application executable was not found' }
    $runnerExecutable = (Resolve-Path -LiteralPath $ExecutablePath).Path
    $projectDirectory = Split-Path -Parent $runnerExecutable
    $runnerArguments = '--tray'
} else {
    $runnerExecutable = Join-Path $projectDirectory '.venv\Scripts\pythonw.exe'
    $runner = Join-Path $projectDirectory 'run_hidden.pyw'
    if (-not (Test-Path -LiteralPath $runnerExecutable)) { throw "pythonw.exe was not found at $runnerExecutable" }
    if (-not (Test-Path -LiteralPath $runner)) { throw "Autostart runner was not found at $runner" }
    $runnerArguments = '"' + $runner + '"'
}

$action = New-ScheduledTaskAction `
    -Execute $runnerExecutable `
    -Argument $runnerArguments `
    -WorkingDirectory $projectDirectory
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
$principal = New-ScheduledTaskPrincipal `
    -UserId $userId `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description 'Publishes the active PS3 game from PSN to Discord Rich Presence.' `
    -Force | Out-Null

if ($StartNow -and -not $NoStart) {
    Start-ScheduledTask -TaskName $taskName
    Write-Host "Installed and started scheduled task: $taskName"
} else {
    Write-Host "Installed scheduled task: $taskName"
}
Write-Host "Log file: $(Join-Path $projectDirectory 'logs\bridge.log')"
