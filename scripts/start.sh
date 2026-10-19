#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
if [[ ! -x .venv/bin/python ]]; then
  echo 'Create the local virtual environment and install requirements first; see README.md.' >&2
  exit 1
fi
.venv/bin/python scripts/check_environment.py
exec .venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port "${1:-8000}"
