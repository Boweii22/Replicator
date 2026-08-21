$ErrorActionPreference = "Stop"
if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python -m pip install -e ".[dev]"
& .\.venv\Scripts\python -m uvicorn services.api.main:app --reload --port 8080

