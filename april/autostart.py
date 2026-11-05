"""Install/remove only APRIL's opt-in XDG desktop-login entry."""
import argparse
import os
from pathlib import Path

MARKER = 'X-APRIL-Managed=true'


def desktop_argument(value):
    """Freedesktop Exec quoting is not shell quoting; escape literal field codes."""
    value = str(value).replace('%', '%%')
    for character in ['\\', '"', '`', '$']:
        value = value.replace(character, '\\' + character)
    return '"' + value + '"'


def install(root, directory, *, remove=False):
    root, directory = Path(root).resolve(), Path(directory)
    path = directory / 'april.desktop'
    if path.is_symlink():
        raise ValueError('Refusing a symlinked autostart entry')
    if path.exists() and MARKER not in path.read_text().splitlines():
        raise ValueError('An unrelated april.desktop entry exists; it was not replaced')
    if remove:
        if path.exists():
            path.unlink()
        return path
    if not (root / 'april.sh').is_file():
        raise ValueError('Run from the APRIL project directory')
    if any(c in str(root) for c in '\n\r'):
        raise ValueError('Project path cannot contain a newline')
    directory.mkdir(parents=True, exist_ok=True)
    # Explicit env preserves the absolute configuration even if KDE starts in HOME.
    command = ['/usr/bin/env', 'APRIL_CONFIG=' + str(root / 'april.local.toml'),
               'bash', str(root / 'april.sh'), '--widget', '--with-search', '--hidden']
    text = ('[Desktop Entry]\nType=Application\nName=APRIL Companion\n'
            'Comment=Local voice companion and wake listener\n'
            'Exec=' + ' '.join(desktop_argument(arg) for arg in command) + '\n'
            'Terminal=false\nStartupNotify=false\n' + MARKER + '\n')
    # Exclusive initial creation; replace only an entry carrying our marker.
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'w') as file:
        file.write(text)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'remove'])
    args = parser.parse_args()
    directory = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'autostart'
    try:
        path = install(Path.cwd(), directory, remove=args.action == 'remove')
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')
    print(('Installed: ' if args.action == 'install' else 'Removed: ') + str(path))
    if args.action == 'install':
        print('Runs after desktop login. Test manually first. Docker and Ollama must already be running.')
        print('On CachyOS, enable your existing services explicitly: sudo systemctl enable --now docker ollama')
        print('Remove login startup: .venv/bin/python -m april.autostart remove')


if __name__ == '__main__':
    main()
