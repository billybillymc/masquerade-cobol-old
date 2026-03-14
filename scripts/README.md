# Script Runner

Use `scripts/dev.ps1` for local orchestration.

## Commands

- `powershell -File scripts/dev.ps1 setup`  
  Install editable dependencies for all three Python services.
- `powershell -File scripts/dev.ps1 start`  
  Start policy-gateway, analysis-orchestrator, and validation-harness.
- `powershell -File scripts/dev.ps1 status`  
  Show running status and ports.
- `powershell -File scripts/dev.ps1 e2e`  
  Run local end-to-end flow check.
- `powershell -File scripts/dev.ps1 smoke`  
  Run smoke tests across services.
- `powershell -File scripts/dev.ps1 stop`  
  Stop managed services and clean pid files.
