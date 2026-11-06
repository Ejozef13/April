#!/usr/bin/env bash
# Use April's interpreter and configuration from any local project directory.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo 'April environment missing. Run bash scripts/setup.sh from the April repository first.' >&2
  exit 1
fi
exec .venv/bin/python -m april.memory "$@"
