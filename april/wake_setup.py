"""Explicit official wake-model download; no silent downloads during startup."""
import argparse
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile

import httpx

MODEL = 'vosk-model-small-en-us-0.15'
URL = 'https://alphacephei.com/vosk/models/' + MODEL + '.zip'


def extract(archive, destination):
    """Validate the entire archive before writing; never follow archive symlinks."""
    with zipfile.ZipFile(archive) as zipped:
        entries = zipped.infolist()
        if len(entries) > 1000 or sum(e.file_size for e in entries) > 300_000_000:
            raise ValueError('Unexpected wake-model archive size')
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if (path.is_absolute() or '..' in path.parts or not path.parts
                    or path.parts[0] != MODEL or '\\' in entry.filename
                    or stat.S_ISLNK(entry.external_attr >> 16)):
                raise ValueError('Unsafe model archive')
        zipped.extractall(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true', required=True,
                        help='Download ~40 MB official Vosk model; review model/license at https://alphacephei.com/vosk/models')
    parser.parse_args()
    root = Path('models')
    root.mkdir(exist_ok=True)
    target = root / MODEL
    if target.exists():
        parser.exit(1, 'Wake model path already exists; it was not replaced. Review it before retrying.\n')
    try:
        with tempfile.TemporaryDirectory(prefix='.april-wake-', dir=root) as directory:
            temporary = Path(directory)
            archive = temporary / 'model.zip'
            with httpx.stream('GET', URL, timeout=60, follow_redirects=False) as response:
                response.raise_for_status()
                count = 0
                with archive.open('wb') as output:
                    for chunk in response.iter_bytes():
                        count += len(chunk)
                        if count > 70_000_000:
                            raise ValueError('Download exceeds model size bound')
                        output.write(chunk)
            extract(archive, temporary)
            candidate = temporary / MODEL
            if not (candidate / 'am/final.mdl').is_file():
                raise ValueError('Wake model acoustic data missing')
            # A user-created target appearing during download must be preserved.
            target.mkdir()
            try:
                for child in candidate.iterdir():
                    shutil.move(str(child), target / child.name)
            except Exception:
                # Leave the partial model for review; never delete an unrelated path.
                raise ValueError('Incomplete wake-model install; review the target before retrying')
    except (httpx.HTTPError, ValueError, OSError, zipfile.BadZipFile):
        parser.exit(1, 'Wake model setup failed. Check network access and the model path; existing models were not overwritten.\n')
    print('Wake model installed locally. No wake accuracy or hardware compatibility has been measured yet.')


if __name__ == '__main__':
    main()
