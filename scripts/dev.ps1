$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$RuntimeDir = Join-Path $PSScriptRoot ".runtime"
$Services = @(
  @{
    Name = "policy-gateway"
    WorkDir = Join-Path $Root "services/policy-gateway"
    App = "app.main:app"
    Port = 8010
  },
  @{
    Name = "analysis-orchestrator"
    WorkDir = Join-Path $Root "services/analysis-orchestrator"
    App = "app.main:app"
    Port = 8011
  },
  @{
    Name = "validation-harness"
    WorkDir = Join-Path $Root "services/validation-harness"
    App = "app.main:app"
    Port = 8012
  }
)

function Ensure-RuntimeDir {
  if (-not (Test-Path $RuntimeDir)) {
    New-Item -ItemType Directory -Path $RuntimeDir | Out-Null
  }
}

function PidPath([string]$name) {
  return Join-Path $RuntimeDir "$name.pid"
}

function LogPath([string]$name) {
  return Join-Path $RuntimeDir "$name.log"
}

function ErrLogPath([string]$name) {
  return Join-Path $RuntimeDir "$name.err.log"
}

function Wait-ForHealth([int]$port, [int]$maxSeconds = 20) {
  $deadline = (Get-Date).AddSeconds($maxSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      Invoke-RestMethod -Uri "http://127.0.0.1:$port/healthz" -TimeoutSec 2 | Out-Null
      return $true
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
  return $false
}

function Start-All {
  Ensure-RuntimeDir
  foreach ($svc in $Services) {
    $pidFile = PidPath $svc.Name
    if (Test-Path $pidFile) {
      Write-Host "$($svc.Name) appears to already be running (pid file exists)."
      continue
    }
    $logFile = LogPath $svc.Name
    $errLogFile = ErrLogPath $svc.Name
    if (Test-Path $logFile) {
      Remove-Item $logFile -Force
    }
    if (Test-Path $errLogFile) {
      Remove-Item $errLogFile -Force
    }
    $proc = Start-Process -FilePath "python" -ArgumentList @(
      "-m", "uvicorn", $svc.App, "--host", "127.0.0.1", "--port", "$($svc.Port)"
    ) -WorkingDirectory $svc.WorkDir -PassThru -RedirectStandardOutput $logFile -RedirectStandardError $errLogFile
    $proc.Id | Out-File -FilePath $pidFile -Encoding ascii
    if (Wait-ForHealth -port $svc.Port) {
      Write-Host "Started $($svc.Name) on port $($svc.Port) (pid $($proc.Id))."
    } else {
      Write-Host "Failed to start $($svc.Name) cleanly. Check log: $logFile"
      try {
        Stop-Process -Id $proc.Id -ErrorAction SilentlyContinue
      } catch {}
      if (Test-Path $pidFile) {
        Remove-Item $pidFile -Force
      }
    }
  }
}

function Setup-All {
  foreach ($svc in $Services) {
    Push-Location $svc.WorkDir
    python -m pip install -e ".[dev]"
    Pop-Location
  }
}

function Stop-All {
  foreach ($svc in $Services) {
    $pidFile = PidPath $svc.Name
    if (-not (Test-Path $pidFile)) {
      Write-Host "$($svc.Name) is not running (no pid file)."
      continue
    }
    $procId = Get-Content $pidFile | Select-Object -First 1
    if ($procId) {
      try {
        Stop-Process -Id $procId -ErrorAction Stop
        Write-Host "Stopped $($svc.Name) (pid $procId)."
      } catch {
        Write-Host "Process $procId already stopped for $($svc.Name)."
      }
    }
    Remove-Item $pidFile -Force
  }
}

function Status-All {
  foreach ($svc in $Services) {
    $pidFile = PidPath $svc.Name
    if (-not (Test-Path $pidFile)) {
      Write-Host "$($svc.Name): stopped"
      continue
    }
    $procId = Get-Content $pidFile | Select-Object -First 1
    $running = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($running) {
      Write-Host "$($svc.Name): running (pid $procId, port $($svc.Port))"
    } else {
      Write-Host "$($svc.Name): stale pid file"
    }
  }
}

function Run-Smoke {
  & (Join-Path $PSScriptRoot "ci-smoke.ps1")
}

function Run-E2E {
  python (Join-Path $PSScriptRoot "e2e/run-flow.py")
}

$command = if ($args.Count -gt 0) { $args[0].ToLowerInvariant() } else { "help" }

switch ($command) {
  "setup" { Setup-All; break }
  "start" { Start-All; break }
  "stop" { Stop-All; break }
  "status" { Status-All; break }
  "smoke" { Run-Smoke; break }
  "e2e" { Run-E2E; break }
  default {
    Write-Host "Usage: powershell -File scripts/dev.ps1 <setup|start|stop|status|smoke|e2e>"
    exit 1
  }
}
