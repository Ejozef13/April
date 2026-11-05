#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  echo 'APRIL needs its Python environment. See README.md installation; do not replace your system Python.' >&2
  exit 1
fi
case "${1:-}" in
  start|stop|status) exec .venv/bin/python -m april.power "$@" ;;
esac
exec .venv/bin/python -m april.launch "$@"
