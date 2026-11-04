#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv --python 3.12 --seed .venv
  elif [[ -x "$HOME/.local/bin/uv" ]]; then
    "$HOME/.local/bin/uv" venv --python 3.12 --seed .venv
  elif command -v python3.12 >/dev/null 2>&1; then
    python3.12 -m venv .venv
  else
    echo 'Python 3.12 is required for the tested environment. Install uv, then rerun; your system Python will not be changed.' >&2
    exit 1
  fi
fi
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m unittest discover -s tests -v
