<#
Installs Flow Voice for the current user: no administrator rights, nothing outside your profile.

  Copies this folder to %LOCALAPPDATA%\Programs\FlowVoice, adds a Start Menu shortcut and starts it.
  Your settings and history live in %APPDATA%\FlowVoice and are never touched by install or uninstall.

  .\Install-FlowVoice.ps1              install (or update in place) and start
  .\Install-FlowVoice.ps1 -Uninstall   remove the program, shortcut and start-with-Windows entry
#>
param([switch]$Uninstall, [switch]$NoStart)
$ErrorActionPreference = "Stop"
$target = Join-Path $env:LOCALAPPDATA "Programs\FlowVoice"
$shortcut = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Flow Voice.lnk"
$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"

function Stop-FlowVoice {
    $running = Get-Process FlowVoice -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$target\*" }
    if ($running) { $running | Stop-Process -Force; Start-Sleep -Seconds 1 }
}

if ($Uninstall) {
    Stop-FlowVoice
    if (Test-Path $shortcut) { Remove-Item $shortcut -Force }
    Remove-ItemProperty -Path $runKey -Name FlowVoice -ErrorAction SilentlyContinue
    if (Test-Path $target) { Remove-Item $target -Recurse -Force }
    Write-Host "Flow Voice removed. Your settings and history in $env:APPDATA\FlowVoice were kept."
    return
}

$source = $PSScriptRoot
if (-not (Test-Path (Join-Path $source "FlowVoice.exe"))) { throw "Run this from the unzipped FlowVoice folder (FlowVoice.exe not found next to it)." }
$sameFolder = $false
if (Test-Path $target) { $sameFolder = ((Resolve-Path $source).Path -eq (Resolve-Path $target).Path) }
if (-not $sameFolder) {
    Stop-FlowVoice
    New-Item -ItemType Directory -Force $target | Out-Null
    Copy-Item (Join-Path $source "*") $target -Recurse -Force
}
$exe = Join-Path $target "FlowVoice.exe"
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($shortcut)
$link.TargetPath = $exe
$link.WorkingDirectory = $target
$link.Description = "Flow Voice - local voice dictation"
$link.Save()
# Keep an existing start-with-Windows entry pointing at the installed copy.
if (Get-ItemProperty -Path $runKey -Name FlowVoice -ErrorAction SilentlyContinue) {
    Set-ItemProperty -Path $runKey -Name FlowVoice -Value ('"' + $exe + '"')
}
Write-Host "Installed to $target"
if (-not $NoStart) { Start-Process $exe -WorkingDirectory $target; Write-Host "Started. Look for the microphone icon in the system tray." }
