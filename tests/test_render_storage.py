import io
import uuid

import pytest
from PIL import Image
from services.api.database import SessionLocal, init_db, normalize_database_url
from services.api.models import Evidence, EvidenceContent
from scripts.run_render import validate


def test_database_photo_survives_local_directory_change_and_is_private(login, monkeypatch, tmp_path):
    monkeypatch.setenv('CIVIC_EVIDENCE_STORAGE', 'database')
    citizen = login('citizen')
    result = citizen.post('/api/v1/reports', json={'domain': 'water', 'zone_id': 'river', 'title': 'Synthetic durable photo',
        'description': 'Synthetic database evidence persistence test', 'location': 'Synthetic test only', 'idempotency_key': str(uuid.uuid4())})
    assert result.status_code == 201
    case = result.json()['case_id']
    stream = io.BytesIO(); Image.new('RGB', (12, 12), 'blue').save(stream, 'PNG')
    key = str(uuid.uuid4())
    def upload():
        return citizen.post('/api/v1/cases/'+case+'/evidence', files={'file': ('test.png', stream.getvalue(), 'image/png')}, data={'notes': 'Synthetic durable evidence', 'idempotency_key': key})
    first = upload(); assert first.status_code == 200, first.text
    second = upload(); assert second.json()['id'] == first.json()['id']
    with SessionLocal() as db:
        record = db.get(EvidenceContent, first.json()['id'])
        expected = record.content
        assert record.byte_count == len(expected)
        assert not (tmp_path / db.get(Evidence, first.json()['id']).filename).exists()
    # New process filesystem cannot provide the photo; the relational data can.
    monkeypatch.setattr('services.api.main.DATA_DIR', tmp_path)
    init_db(); init_db()
    response = citizen.get(first.json()['url'])
    assert response.status_code == 200 and response.content == expected
    assert response.headers['content-type'].startswith('image/jpeg')
    assert response.headers['cache-control'] == 'no-store'
    assert login('inspector').get(first.json()['url']).status_code == 403


def test_render_free_configuration_rejects_ephemeral_storage_and_demo():
    env = {'DATABASE_URL': 'postgresql://user:synthetic@example.invalid/db?sslmode=require', 'COOKIE_SECURE': 'true',
           'CIVIC_DEMO_MODE': 'false', 'CIVIC_EVIDENCE_STORAGE': 'database', 'PORT': '10000'}
    assert validate(env) == 10000
    for key, value in [('DATABASE_URL', 'sqlite:///lost.db'), ('CIVIC_EVIDENCE_STORAGE', 'filesystem'), ('CIVIC_DEMO_MODE', 'true'), ('COOKIE_SECURE', 'false'), ('PORT', 'invalid')]:
        with pytest.raises(ValueError):
            validate({**env, key: value})
    assert normalize_database_url(env['DATABASE_URL']) == env['DATABASE_URL'].replace('postgresql://', 'postgresql+psycopg://')
    assert normalize_database_url('postgres://host/db') == 'postgresql+psycopg://host/db'
    assert normalize_database_url('sqlite:///local.db') == 'sqlite:///local.db'
