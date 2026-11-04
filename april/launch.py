"""One desktop entry point; fails early with explicit repair steps."""
import argparse
import asyncio
import os
from pathlib import Path

from .config import load_config
from .readiness import check_readiness


def main():
    parser = argparse.ArgumentParser(description='Start APRIL with read-only prerequisite checks.')
    parser.add_argument('--simulation', action='store_true', help='Explicitly use fixtures without speech/models')
    parser.add_argument('--check', action='store_true', help='Check prerequisites without starting the server')
    args = parser.parse_args()
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
    if not args.check:
        from .server import main as serve
        serve()


if __name__ == '__main__':
    main()
