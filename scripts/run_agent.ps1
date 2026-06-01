$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Missing .venv. Creating it first..."
    & (Join-Path $PSScriptRoot "setup_venv.ps1")
}

Set-Location $ProjectRoot
& $VenvPython bank_agent.py --input-dir .\input --output-dir .\output
