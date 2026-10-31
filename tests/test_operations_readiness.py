import time
from datetime import datetime, timedelta, timezone

import pytest

from services.api.database import SessionLocal
from services.api.models import Audit, Case, Configuration, Evidence, Reading, Report, Session, Upload
from services.api.operations_readiness import worker_heartbeat


@pytest.fixture
def policy_guard():
    with SessionLocal() as db:
        old = db.get(Configuration, 'temporary-retention')
        saved = (old.value, old.version) if old else None
    yield
    with SessionLocal() as db:
        row = db.get(Configuration, 'temporary-retention')
        if saved:
            row.value, row.version = saved
        elif row:
            db.delete(row)
        db.query(Upload).filter(Upload.id.like('retention-test-%')).delete(synchronize_session=False)
        db.query(Session).filter(Session.token_hash.like('retention-test-%')).delete(synchronize_session=False)
        db.commit()


def configure(admin, enabled=True):
    policy = admin.get('/api/v1/operations/retention').json()
    response = admin.post('/api/v1/operations/retention', json={
        'version': policy['version'], 'enabled': enabled, 'expired_session_grace_hours': 24,
        'uncommitted_upload_days': 30, 'basis': 'Synthetic acceptance test policy, not a municipal policy',
        'reason': 'Explicitly configure temporary records for this synthetic test',
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_retention_requires_admin_and_enabled_versioned_policy(login, policy_guard):
    citizen, admin = login('citizen'), login('admin')
    for path in ['retention', 'retention/preview', 'readiness']:
        assert citizen.get('/api/v1/operations/' + path).status_code == 403
    policy = configure(admin, False)
    assert admin.get('/api/v1/operations/retention/preview').status_code == 409
    payload = {**policy, 'reason': 'Attempt stale policy update', 'version': policy['version'] - 1}
    assert admin.post('/api/v1/operations/retention', json=payload).status_code == 409
    payload['version'] = policy['version']
    assert citizen.post('/api/v1/operations/retention', json=payload).status_code == 403
    payload['uncommitted_upload_days'] = 0
    assert admin.post('/api/v1/operations/retention', json=payload).status_code == 422


def seed_temporary():
    old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    with SessionLocal() as db:
        db.add_all([
            Session(token_hash='retention-test-expired', user_id='demo-citizen', csrf='synthetic', expires_at=time.time() - 172800),
            Session(token_hash='retention-test-active', user_id='demo-citizen', csrf='synthetic', expires_at=time.time() + 86400),
            Upload(id='retention-test-old', user_id='demo-operator', checksum='synthetic', rows=[], errors=[], status='preview', created_at=old),
            Upload(id='retention-test-committed', user_id='demo-operator', checksum='synthetic', rows=[], errors=[], status='committed', created_at=old),
            Upload(id='retention-test-new', user_id='demo-operator', checksum='synthetic', rows=[], errors=[], status='preview'),
        ])
        db.commit()


def test_cleanup_preview_execute_preserves_evidence_and_active_records(login, policy_guard):
    admin = login('admin'); configure(admin); seed_temporary()
    with SessionLocal() as db:
        counts = {model: db.query(model).count() for model in [Case, Report, Evidence, Reading]}
    preview = admin.get('/api/v1/operations/retention/preview').json()
    assert preview['expired_sessions'] >= 1 and preview['uncommitted_uploads'] >= 1
    assert 'token_hash' not in str(preview) and 'retention-test-old' not in str(preview)
    body = {'version': preview['version'], 'confirmation': preview['confirmation'], 'reason': 'Delete only explicitly previewed temporary synthetic records'}
    assert login('operator').post('/api/v1/operations/retention/execute', json=body).status_code == 403
    response = admin.post('/api/v1/operations/retention/execute', json=body)
    assert response.status_code == 200, response.text
    assert admin.post('/api/v1/operations/retention/execute', json=body).status_code == 409
    with SessionLocal() as db:
        assert db.get(Session, 'retention-test-expired') is None
        assert db.get(Session, 'retention-test-active')
        assert db.get(Upload, 'retention-test-old') is None
        assert db.get(Upload, 'retention-test-committed')
        assert db.get(Upload, 'retention-test-new')
        assert all(db.query(model).count() == count for model, count in counts.items())
        assert db.query(Audit).filter_by(action='temporary_retention_cleanup').count() >= 1


def test_changed_preview_requires_review_and_never_deletes_committed_upload(login, policy_guard):
    admin = login('admin'); configure(admin); seed_temporary()
    preview = admin.get('/api/v1/operations/retention/preview').json()
    with SessionLocal() as db:
        db.get(Upload, 'retention-test-old').status = 'committed'
        db.commit()
    response = admin.post('/api/v1/operations/retention/execute', json={'version': preview['version'], 'confirmation': preview['confirmation'], 'reason': 'Try obsolete cleanup preview after an import commit'})
    assert response.status_code == 409
    with SessionLocal() as db:
        assert db.get(Session, 'retention-test-expired')
        assert db.get(Upload, 'retention-test-old').status == 'committed'


def test_readiness_distinguishes_worker_activity_without_exposing_secrets(login):
    admin = login('admin')
    with SessionLocal() as db:
        worker_heartbeat(db)
    response = admin.get('/api/v1/operations/readiness')
    assert response.status_code == 200
    body = response.json()
    assert body['worker']['state'] == 'recent'
    assert 'password' not in response.text.lower() and 'token_hash' not in response.text
    with SessionLocal() as db:
        row = db.get(Configuration, 'worker-heartbeat')
        row.value = {**row.value, 'epoch': time.time() - 901}; db.commit()
    assert admin.get('/api/v1/operations/readiness').json()['worker']['state'] == 'stale'
    with SessionLocal() as db:
        worker_heartbeat(db)


def test_browser_security_headers_and_api_no_store(server):
    response = server.get('/api/v1/health')
    policy = response.headers['Content-Security-Policy']
    assert "script-src 'self'" in policy and "object-src 'none'" in policy
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.headers['X-Frame-Options'] == 'DENY'
