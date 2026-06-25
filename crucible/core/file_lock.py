"""Cross-process exclusive file lock using fcntl."""
import fcntl
from pathlib import Path


class FileLock:
    def __init__(self, path: Path):
        self._lock_path = path.with_suffix('.lock')
        self._fh = None

    def __enter__(self):
        self._fh = open(self._lock_path, 'w')
        fcntl.flock(self._fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_):
        fcntl.flock(self._fh, fcntl.LOCK_UN)
        self._fh.close()
