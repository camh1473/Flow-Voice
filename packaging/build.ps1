<#
Builds dist\FlowVoice\ (a self-contained folder with FlowVoice.exe) and FlowVoice-<version>.zip.

  .\packaging\build.ps1                       # uses E:\Build\flowvoice-build for the build environment
  .\packaging\build.ps1 -Model small.en       # which speech model to ship inside (default: the config default)
  .\packaging\build.ps1 -NoModel              # smaller; the model is downloaded on first run instead

Everything is installed into the build environment only, never into the project's .venv.
#>
param(
    [string]$BuildRoot = "E:\Build\flowvoice-build",
    [string]$Model = "small.en",
    [switch]$NoModel,
    [string]$Python = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $BuildRoot "venv"
$work = Join-Path $BuildRoot "work"
$dist = Join-Path $repo "dist"

Write-Host "1/5 build environment: $venv"
if (-not (Test-Path "$venv\Scripts\python.exe")) {
    uv venv $venv --python $Python
    if ($LASTEXITCODE) { throw "uv venv failed" }
}
uv pip install --python "$venv\Scripts\python.exe" -r "$repo\requirements-lock.txt" pyinstaller
if ($LASTEXITCODE) { throw "dependency install failed" }
uv pip install --python "$venv\Scripts\python.exe" --no-deps "$repo"
if ($LASTEXITCODE) { throw "project install failed" }

Write-Host "2/5 PyInstaller"
if (Test-Path "$dist\FlowVoice") { Remove-Item "$dist\FlowVoice" -Recurse -Force }
& "$venv\Scripts\python.exe" -m PyInstaller "$repo\packaging\flowvoice.spec" --noconfirm --distpath $dist --workpath $work
if ($LASTEXITCODE) { throw "PyInstaller failed" }

if (-not $NoModel) {
    Write-Host "3/5 bundling speech model $Model"
    $roots = @($env:HF_HUB_CACHE, "E:\Cache\huggingface\hub", "$env:USERPROFILE\.cache\huggingface\hub") | Where-Object { $_ }
    $snap = $null
    foreach ($root in $roots) {
        $snap = Get-ChildItem "$root\models--Systran--faster-whisper-$Model\snapshots" -Directory -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($snap) { break }
    }
    if (-not $snap) { throw "Model $Model is not in the Hugging Face cache. Run the app once with it, or use -NoModel." }
    $target = "$dist\FlowVoice\models\$Model"
    New-Item -ItemType Directory -Force $target | Out-Null
    Get-ChildItem $snap.FullName | ForEach-Object { Copy-Item $_.FullName $target -Force }
} else { Write-Host "3/5 model not bundled (-NoModel)" }

Write-Host "4/5 install script"
Copy-Item "$repo\packaging\Install-FlowVoice.ps1" "$dist\FlowVoice\Install-FlowVoice.ps1" -Force
Copy-Item "$repo\packaging\Install-FlowVoice.cmd" "$dist\FlowVoice\Install-FlowVoice.cmd" -Force

Write-Host "5/5 zip"
$ver = (Select-String -Path "$repo\pyproject.toml" -Pattern '^version\s*=\s*"(.+)"').Matches[0].Groups[1].Value
$zip = Join-Path $dist "FlowVoice-$ver.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path "$dist\FlowVoice" -DestinationPath $zip -CompressionLevel Optimal
$size = [math]::Round((Get-Item $zip).Length / 1MB)
Write-Host "Done: $dist\FlowVoice\FlowVoice.exe and $zip ($size MB)"
