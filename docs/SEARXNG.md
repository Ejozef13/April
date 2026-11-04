# Local SearXNG for APRIL

SearXNG is the selected default web provider. It is free/open-source software with no search API subscription, but it consumes your existing compute/network resources and depends on upstream engines. It is not an unlimited-search guarantee or proven equivalent to Brave. We keep Brave selectable for a later comparison; no automatic paid-provider fallback exists.

## Desktop setup

Use the CachyOS desktop first, not the Pi. Docker Engine plus Compose v2 must be installed, running and accessible through your approved local socket. The helper does not install Docker, restart its daemon, change group membership, or stop AM/Ollama.

If Docker is absent, the CachyOS repository packages are `docker` and `docker-compose`. Check your existing installation first. If installation is needed:

```bash
sudo pacman -S --needed docker docker-compose
```

If the existing Docker service is stopped, start it explicitly with `sudo systemctl start docker`. If socket access is denied, report the exact error so we can use your existing access/rootless setup; do not run APRIL's helper with sudo or change unrelated services blindly. Keep package signatures and TLS verification enabled.

Stop APRIL itself with Ctrl+C. From the repository:

```bash
cd ~/Projects/April
bash scripts/searxng.sh up
.venv/bin/python -m april.integrations search-provider searxng
bash april.sh
```

The Docker helper creates only APRIL Search's project/service and its own ignored state under `artifacts/searxng`. It publishes **127.0.0.1:8888 → container port 8080**, not a public/LAN listener. APRIL remains on port 8765. It runs as your user, with one worker, a one-CPU limit and a 512 MiB memory limit; these are limits, not measured performance claims. The official image is pinned by digest in `deploy/searxng/compose.yaml`.

First-time initialization enables `[html, json]` output and generates a private random signing secret. Existing settings and secrets are preserved on repeat runs. This private single-user instance disables the public-instance limiter and requires no Redis/Valkey container; do not reuse that configuration as an exposed public service. The selected engine set is DuckDuckGo, Brave’s public web engine and Wikipedia, with Wikipedia list results enabled. These do not use the paid Brave Search API adapter or a Brave API key. Upstream defaults currently disable Bing/Google, so we do not silently enable those disabled engines. Review engines on your own instance if results are insufficient; do not bypass CAPTCHAs/rate limits.

The service root is read-only with dedicated writable config/cache mounts and a temporary filesystem. It has no GPU devices, mail credentials, document folders or Docker socket mounted inside it. Logs rotate; review/redact them before sharing because engine errors may contain query details.

## Verify real search

Refresh APRIL. The search panel should identify **web (searxng)**. Ask:

> April, search the web for the Linux kernel official website.

Open Retrieved sources and confirm actual URLs/excerpts. Then try a precise current-fact query specifying the country, such as the current president of the United States. Results may be incomplete/outdated; citations and search snippets still need review.

The helper's healthy status only verifies the local HTTP service, not successful upstream search. For a direct test without model generation:

```bash
.venv/bin/python -c 'import httpx; r=httpx.post("http://127.0.0.1:8888/search",data={"q":"Linux kernel official website","format":"json"},timeout=15,trust_env=False); r.raise_for_status(); d=r.json(); print("Results:",len(d.get("results",[]))); print("Engine errors:",d.get("unresponsive_engines",[]))'
```

APRIL sends queries to the local JSON API using POST, takes at most three bounded results, and passes excerpts to the loopback model. No Brave key or proxy credential is forwarded to SearXNG by the adapter. The search service contacts upstream engines, which can see queries and the service's network IP. Private document/Gmail excerpts are never silently used as web queries.

## Manage only APRIL Search

```bash
bash scripts/searxng.sh status
bash scripts/searxng.sh stop
```

Stop preserves its cache/config and affects only this project's service. Do not stop the Docker daemon or prune shared containers/volumes. `restart: unless-stopped` restarts this container when Docker starts if you have not explicitly stopped it; this does not enable the Docker service at boot.

If port 8888 is already used, do not stop that application. Choose a free port, update only `APRIL_SEARCH_PORT` in ignored `artifacts/searxng/compose.env`, rerun `up`, then select the matching URL:

```bash
.venv/bin/python -m april.integrations search-provider searxng --url http://127.0.0.1:8889
```

Custom URLs are restricted to loopback, with no credentials/path/query. An authenticated local tunnel may reach a future home-server instance; public/unauthenticated remote instances are not supported by this adapter. For an existing approved rootless Docker setup, explicitly select its local Unix socket with `APRIL_DOCKER_HOST`. The helper ignores inherited remote Docker contexts and rejects remote TCP/SSH daemon endpoints.

## Brave later

No need to remove or replace any existing Brave key:

```bash
.venv/bin/python -m april.integrations search-provider brave
```

Follow INTEGRATIONS.md to configure its key if needed, then restart APRIL. Switching providers preserves the model, approved document folders, Gmail settings and stored credentials. Only the explicitly selected provider is called. Compare a fixed set of questions, source usefulness, failures and latency before deciding which is better; no comparative score has been measured.

## Validation and upstream references

The cloud pulled the official image and verified its digest, then started the real service as the normal user with the configured limits. `/healthz` returned 200 and `/search` returned JSON 200. Engine results were empty with connection errors. Independent outbound checks to DuckDuckGo/Wikipedia returned explicit proxy CONNECT 403 denials; container proxy/CA variables were present. This is evidence of a cloud-network restriction, not a result-quality comparison. No TLS verification or engine restriction was bypassed. Real desktop search remains pending.

Cloud-only tests supplied the session's trusted combined CA bundle through an explicit untracked Compose override. The helper supports `APRIL_SEARCH_COMPOSE_OVERRIDE` for that purpose; the ordinary desktop setup does not copy cloud-specific proxy/CA settings. The service lifecycle helper was run twice with settings preserved.

Sources inspected: [official defaults](https://github.com/searxng/searxng/blob/master/searx/settings.yml), [container Dockerfile/entrypoint](https://github.com/searxng/searxng/tree/master/container), [network client trust handling](https://github.com/searxng/searxng/blob/master/searx/network/client.py), [JSON API documentation](https://docs.searxng.org/dev/search_api.html). SearXNG uses AGPL-3.0-or-later; the official container is a separate dependency, not bundled proprietary artwork/software. Physical Pi image compatibility and rendering/inference contention are separate future checks.


### Automatic web lookup

Ordinary live voice and text requests now search the configured provider before
generating a response. Clock requests use the real local clock; explicit file and
Gmail searches keep their dedicated routes. Common private cues (such as “my
emails”, home paths and email addresses) suppress automatic web lookup. This is a
routing heuristic, not a complete detector of sensitive information: ordinary
prompts go to upstream search engines, so avoid including secrets. Retrieved
private excerpts are never automatically forwarded to web search.

The UI reports lookup progress and shows actual retrieved sources separately
from model prose. Failed or empty searches do not fall back to an unsupported
model answer. Search snippets can still be incomplete or wrong; review sources.
“Check on the internet” is now recognized as an explicit search request.

Set `automatic_web_search = false` in ignored `april.local.toml` and restart to
use local conversation with explicit search controls (also suitable for offline
operation). Current-fact guards still require retrieval. Simulation never
performs automatic searches.

If startup says Docker is unavailable or inaccessible, run
`sudo systemctl start docker`, then
`docker --host=unix:///var/run/docker.sock info --format '{{.ServerVersion}}'`.
If the second command fails, inspect its printed error before changing socket
permissions. Do not run APRIL or the whole setup helper as root.
