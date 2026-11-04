"""Read-only prerequisite checks. Never start services or load/unload models."""
import shutil
from pathlib import Path

import httpx


def speech_checks(config):
    checks = []
    for name, value in [('Whisper executable', config.whisper_cli), ('Piper executable', config.piper_cli)]:
        checks.append({'component': name, 'ready': shutil.which(value) is not None,
                       'message': 'Available' if shutil.which(value) else 'Missing executable. Check april.local.toml and run bash scripts/setup_speech.sh.'})
    for name, value in [('Whisper model', config.stt_model), ('Piper voice', config.voice),
                        ('Piper voice configuration', config.voice + '.json')]:
        path = Path(value)
        ready = path.is_file() and path.stat().st_size > 0
        checks.append({'component': name, 'ready': ready,
                       'message': 'Present (integrity not verified)' if ready else 'Missing or empty file. Check the configured model/voice path.'})
    return checks


async def check_readiness(config, *, transport=None):
    if config.mode == 'simulation':
        return {'ready': True, 'mode': 'simulation', 'checks': [
            {'component': 'Simulation', 'ready': True, 'message': 'Fixtures only. No real model or speech inference.'}]}
    checks = speech_checks(config)
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=4, transport=transport) as client:
            response = await client.get(config.ollama_url + '/api/tags')
            response.raise_for_status()
            models = response.json()['models']
            names = {m.get('name') for m in models} | {m.get('model') for m in models}
            expected = config.model if ':' in config.model else config.model + ':latest'
            available = config.model in names or expected in names
        checks.append({'component': 'Ollama model', 'ready': available,
                       'message': 'Configured model listed; inference not yet verified.' if available else
                       'Configured model is not listed. Run ollama list and match model in april.local.toml; reuse an installed model.'})
    except httpx.ConnectError:
        checks.append({'component': 'Ollama', 'ready': False,
                       'message': 'Not reachable. Check systemctl status ollama; if stopped, start your existing service with sudo systemctl start ollama, then retry.'})
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        checks.append({'component': 'Ollama', 'ready': False,
                       'message': 'Readiness request failed. Check the configured Ollama address and service; no services were changed.'})
    return {'ready': all(c['ready'] for c in checks), 'mode': config.mode, 'checks': checks}
