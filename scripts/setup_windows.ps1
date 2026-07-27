$ErrorActionPreference = "Stop"
if (-not (Test-Path ".venv")) {
    py -m venv .venv
}
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Write-Host "Environment ready. Run: python -m src.cli run-demo"
