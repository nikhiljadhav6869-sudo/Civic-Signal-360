"""Read-only configuration preflight. It never deploys or prints credentials."""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def evaluate(environment, built, production=False):
    checks = [{'name': 'frontend_build', 'passed': built}]
    if production:
        origin = urlparse(environment.get('CIVIC_PUBLIC_ORIGIN', ''))
        password = environment.get('CIVIC_ADMIN_PASSWORD', '')
        checks.extend([
            {'name': 'demo_disabled', 'passed': environment.get('CIVIC_DEMO_MODE', 'true').lower() == 'false'},
            {'name': 'secure_cookies', 'passed': environment.get('COOKIE_SECURE', 'false').lower() == 'true'},
            {'name': 'public_https_origin', 'passed': origin.scheme == 'https' and bool(origin.hostname) and not origin.username and not origin.password and origin.path in {'', '/'} and not origin.query and not origin.fragment},
            {'name': 'administrator_configured', 'passed': '@' in environment.get('CIVIC_ADMIN_EMAIL', '') and len(password) >= 14 and password != 'CivicDemo!2026'},
            {'name': 'explicit_database', 'passed': bool(environment.get('DATABASE_URL'))},
            {'name': 'explicit_storage', 'passed': bool(environment.get('CIVIC_DATA_DIR'))},
        ])
    return {'scope': 'Software-only configuration preflight', 'mode': 'production' if production else 'local',
            'configuration_checks_passed': all(c['passed'] for c in checks), 'checks': checks,
            'hardware_required': False, 'deployment_verified': False,
            'manual_verification': ['Use separate operational storage; never reuse the demo database.',
                                    'Verify HTTPS, trusted proxy/host configuration, backups and restore, worker activity and load on the actual host.',
                                    'Live email and historical-data accuracy need their own evidence. No email is sent by this check.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--production', action='store_true')
    args = parser.parse_args()
    result = evaluate(os.environ, (ROOT / 'apps/web/dist/index.html').is_file(), args.production)
    print(json.dumps(result, indent=2))
    return 0 if result['configuration_checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
