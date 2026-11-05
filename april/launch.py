"""One desktop entry point; fails early with explicit repair steps."""
import argparse
import asyncio
import os
import subprocess
from pathlib import Path

from .config import load_config
from .readiness import check_readiness


def main():
    parser = argparse.ArgumentParser(description='Start APRIL after prerequisite checks, with optional local search startup.')
    parser.add_argument('--simulation', action='store_true', help='Explicitly use fixtures without speech/models')
    parser.add_argument('--check', action='store_true', help='Check prerequisites without starting the server')
    parser.add_argument('--with-search', action='store_true',
                        help='Start only APRIL Search before launching the live app (requires Docker access)')
    parser.add_argument('--widget', action='store_true', help='Native desktop tray and wake-phrase companion')
    parser.add_argument('--hidden', action='store_true', help='Start the widget in the tray (desktop login)')
    args = parser.parse_args()
    if args.hidden and not args.widget:
        parser.error('--hidden requires --widget')
    if args.widget and args.check:
        parser.error('--widget cannot be combined with --check')
    if args.with_search and (args.simulation or args.check):
        parser.error('--with-search is for live startup; omit it for simulation or read-only checks')
    # Explicit flags win over a stale APRIL_MODE in a terminal session.
    os.environ['APRIL_MODE'] = 'simulation' if args.simulation else 'live'
    local = Path(os.environ.get('APRIL_CONFIG', 'april.local.toml'))
    if not args.simulation and not local.exists():
        profile = Path('april.desktop.example.toml')
        if not profile.exists():
            parser.exit(1, 'Missing local configuration. Create april.local.toml from the repository desktop profile.\n')
        try:
            with local.open('x') as file:
                file.write(profile.read_text())
        except OSError:
            parser.exit(1, 'Cannot create local settings. Check APRIL_CONFIG and directory permissions; existing files were not overwritten.\n')
        print('Created local desktop configuration; existing settings are never overwritten.')
    try:
        config = load_config()
        result = asyncio.run(check_readiness(config))
    except (ValueError, TypeError, OSError, KeyError):
        parser.exit(1, 'Cannot read configuration. Check TOML types, keys, timezone and paths in april.local.toml.\n')
    print(f'APRIL / {config.mode.upper()}')
    for check in result['checks']:
        print(f"[{'OK' if check['ready'] else 'FIX'}] {check['component']}: {check['message']}")
    if not result['ready']:
        parser.exit(1, 'Startup paused. Resolve the checks above and run the same command again.\n')
    if args.with_search:
        # Own service only: do not start/restart Docker or shared Ollama.
        result = subprocess.run(['bash', 'scripts/searxng.sh', 'up'], check=False)
        if result.returncode:
            parser.exit(1, 'Search startup failed. Resolve the helper message and retry; APRIL was not started.\n')
    if args.widget:
        try:
            from .desktop import main as desktop
        except ImportError:
            parser.exit(1, 'Desktop dependencies missing. Run bash scripts/setup_desktop.sh.\n')
        raise SystemExit(desktop(config, hidden=args.hidden))
    if not args.check:
        from .server import main as serve
        serve()


if __name__ == '__main__':
    main()
