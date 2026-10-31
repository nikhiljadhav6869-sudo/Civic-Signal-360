"""Free-tier Render launcher: external database, database photos, no paid disk."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def validate(environment):
    url = environment.get('DATABASE_URL', '')
    if not url.startswith(('postgresql://', 'postgres://', 'postgresql+psycopg://')):
        raise ValueError('Configure an external PostgreSQL database; Render local files are not persistent.')
    if environment.get('CIVIC_EVIDENCE_STORAGE') != 'database':
        raise ValueError('Set CIVIC_EVIDENCE_STORAGE=database to preserve private photographs.')
    if environment.get('CIVIC_DEMO_MODE', 'true').lower() != 'false':
        raise ValueError('Public deployment must not use shared local demo accounts.')
    if environment.get('COOKIE_SECURE', 'false').lower() != 'true':
        raise ValueError('Set COOKIE_SECURE=true for the Render HTTPS endpoint.')
    try:
        port = int(environment.get('PORT', '10000'))
    except ValueError as exc:
        raise ValueError('PORT must be a valid integer.') from exc
    if not 1 <= port <= 65535:
        raise ValueError('PORT must be between 1 and 65535.')
    return port


def main():
    try:
        port = validate(os.environ)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    os.chdir(ROOT)
    # Replace this process: run.py supervises API + worker and handles shutdown.
    os.execv(sys.executable, [sys.executable, 'scripts/run.py', '--host', '0.0.0.0', '--port', str(port)])


if __name__ == '__main__':
    raise SystemExit(main())
