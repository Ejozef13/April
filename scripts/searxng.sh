#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
action="${1:-up}"
case "$action" in up|status|stop) ;; *) echo 'Usage: bash scripts/searxng.sh [up|status|stop]' >&2; exit 1;; esac
if [[ ! -x .venv/bin/python ]]; then
  echo 'Prepare APRIL with bash scripts/setup.sh first.' >&2; exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
  echo 'Docker is not installed. Report this output so we can prepare the desktop runtime without changing existing services blindly.' >&2; exit 1
fi
if [[ "$(id -u)" == 0 ]]; then
  echo 'Run as your normal user with approved Docker access, not sudo; this helper writes user-owned files.' >&2; exit 1
fi
# Never deploy to an inherited remote Docker context by accident. Rootless users
# may explicitly choose their local Unix socket through APRIL_DOCKER_HOST.
daemon="${APRIL_DOCKER_HOST:-unix:///var/run/docker.sock}"
case "$daemon" in unix://*) ;; *) echo 'APRIL_DOCKER_HOST must select an explicit local Unix socket.' >&2; exit 1;; esac
docker_local() {
  env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH \
    docker --host="$daemon" "$@"
}
if ! docker_local info --format '{{.ServerVersion}}' >/dev/null 2>&1; then
  echo 'Local Docker is unavailable or inaccessible. Check systemctl status docker and socket access; no daemon or group settings were changed.' >&2; exit 1
fi
if ! docker_local compose version --short >/dev/null 2>&1; then
  echo 'Docker Compose v2 is missing. On CachyOS the repository package is docker-compose; report the error before changing an existing runtime.' >&2; exit 1
fi
if [[ "$action" == up ]]; then
  .venv/bin/python -m april.searxng_service
elif [[ ! -f artifacts/searxng/compose.env ]]; then
  echo 'No APRIL Search state found. Run bash scripts/searxng.sh up first.' >&2; exit 1
fi
compose_files=(-f deploy/searxng/compose.yaml)
# Optional explicit trust/proxy override for managed test environments. It is
# never created automatically or copied into the ordinary desktop deployment.
if [[ -n "${APRIL_SEARCH_COMPOSE_OVERRIDE:-}" ]]; then
  [[ -f "$APRIL_SEARCH_COMPOSE_OVERRIDE" ]] || { echo 'Compose override file is missing.' >&2; exit 1; }
  compose_files+=(-f "$APRIL_SEARCH_COMPOSE_OVERRIDE")
fi
compose() { docker_local compose --project-name april-search --env-file artifacts/searxng/compose.env "${compose_files[@]}" "$@"; }
case "$action" in
  up) compose up -d --wait --wait-timeout 60 searxng
      echo 'Local server health passed. Verify real JSON search using docs/SEARXNG.md; engine access may still fail.' ;;
  status) compose ps searxng ;;
  stop) compose stop searxng ;;
esac
