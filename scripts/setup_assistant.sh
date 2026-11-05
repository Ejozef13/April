#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo 'Run bash scripts/setup.sh first.' >&2; exit 1
fi
.venv/bin/python -m pip install -r requirements-assistant.lock -r requirements-gmail.lock
echo 'Optional assistant packages installed. OCR also needs Tesseract (CachyOS: sudo pacman -S --needed tesseract tesseract-data-eng).'
echo 'Read docs/ASSISTANT.md before enabling CalDAV, IDE execution or managed startup.'
