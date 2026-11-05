#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo 'Run bash scripts/setup.sh first.' >&2
  exit 1
fi
.venv/bin/python -m pip install -r requirements-desktop.lock
echo 'Desktop packages installed. Linux needs PortAudio (CachyOS: sudo pacman -S --needed portaudio).'
echo 'Download the separate wake model using the instructions in docs/WIDGET.md.'
echo 'Test manually before enabling login startup: bash april.sh --widget --with-search'
