import json
from scripts.check_readiness import evaluate


def test_local_preflight_needs_no_hardware_or_email():
    result = evaluate({}, True)
    assert result['configuration_checks_passed']
    assert result['hardware_required'] is False
    assert result['deployment_verified'] is False
    assert not evaluate({}, False)['configuration_checks_passed']


def test_production_preflight_fails_local_defaults_without_leaking_secrets():
    secret = 'a-unique-synthetic-test-secret'
    result = evaluate({'CIVIC_ADMIN_PASSWORD': secret}, True, True)
    assert not result['configuration_checks_passed']
    assert secret not in json.dumps(result)


def test_production_preflight_checks_configuration_not_deployment():
    environment = {'CIVIC_DEMO_MODE': 'false', 'COOKIE_SECURE': 'true', 'CIVIC_PUBLIC_ORIGIN': 'https://civic.example.test',
                   'CIVIC_ADMIN_EMAIL': 'admin@example.test', 'CIVIC_ADMIN_PASSWORD': 'Synthetic-only-password-93',
                   'DATABASE_URL': 'sqlite:////private/civic.db', 'CIVIC_DATA_DIR': '/private/evidence'}
    result = evaluate(environment, True, True)
    assert result['configuration_checks_passed'] and not result['deployment_verified']
    for bad in ['http://civic.example.test', 'https://user:secret@civic.example.test', 'https://civic.example.test/subpath']:
        assert not evaluate({**environment, 'CIVIC_PUBLIC_ORIGIN': bad}, True, True)['configuration_checks_passed']
