"""Cloud entry point; local Windows uvicorn commands remain unchanged."""
import os
import sys
from pathlib import Path


def main():
    os.environ.setdefault('APP_ENV', 'production')
    if not os.environ.get('DATABASE_URL', '').strip():
        raise SystemExit('Set DATABASE_URL for the cloud backend; no local database fallback here.')
    try:
        port = int(os.environ.get('PORT', '8000'))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise SystemExit('PORT must be an integer from 1 to 65535')
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    os.execv(sys.executable, [sys.executable, '-m', 'uvicorn', 'app.main:app',
                            '--app-dir', 'backend', '--workers', '1', '--host', '0.0.0.0', '--port', str(port)])


if __name__ == '__main__':
    main()
