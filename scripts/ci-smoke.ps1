$ErrorActionPreference = "Stop"

Write-Host "Running policy-gateway smoke tests..."
Push-Location "services/policy-gateway"
python -m pip install -e ".[dev]"
python -m pytest -q
Pop-Location

Write-Host "Running analysis-orchestrator smoke tests..."
Push-Location "services/analysis-orchestrator"
python -m pip install -e ".[dev]"
python -m pytest -q
Pop-Location

Write-Host "Running validation-harness smoke tests..."
Push-Location "services/validation-harness"
python -m pip install -e ".[dev]"
python -m pytest -q
Pop-Location

Write-Host "Smoke tests completed successfully."
