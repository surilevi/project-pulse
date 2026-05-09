$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$configPath = Join-Path $repoRoot "project-pulse.local.toml"
$pythonPath = (Get-Command python -ErrorAction Stop).Source

$existingPythonPath = [Environment]::GetEnvironmentVariable("PYTHONPATH", "Process")
if ([string]::IsNullOrWhiteSpace($existingPythonPath)) {
    $env:PYTHONPATH = (Join-Path $repoRoot "src")
}
else {
    $env:PYTHONPATH = (Join-Path $repoRoot "src") + ";" + $existingPythonPath
}

Set-Location $repoRoot
& $pythonPath "-m" "project_pulse" "codex-watch" "--config" $configPath
