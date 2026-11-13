import io
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
import pytest

from services.api.mobile_install import install_url, router


@pytest.mark.parametrize('value', ['', 'http://example.com', 'https://localhost', 'https://127.0.0.1', 'https://10.0.0.1', 'https://name.local', 'https://name.test', 'https://user:secret@example.com', 'https://example.com/path', 'https://example.com?secret=x', 'https://example.com:bad'])
def test_install_rejects_non_public_or_credential_urls(monkeypatch, value):
    monkeypatch.setenv('CIVIC_PUBLIC_ORIGIN', value)
    monkeypatch.delenv('RENDER_EXTERNAL_URL', raising=False)
    assert install_url() is None


def test_qr_uses_only_configured_origin_and_encodes_install_path(monkeypatch):
    monkeypatch.delenv('CIVIC_PUBLIC_ORIGIN', raising=False)
    monkeypatch.setenv('RENDER_EXTERNAL_URL', 'https://civic-example.onrender.com')
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    result = client.get('/api/v1/install', headers={'Host': 'attacker.example'})
    assert result.json()['url'] == 'https://civic-example.onrender.com/install'
    import services.api.mobile_install as mobile
    original = mobile.qrcode.QRCode.add_data
    payloads = []
    def capture(self, data, *args, **kwargs):
        payloads.append(data)
        return original(self, data, *args, **kwargs)
    monkeypatch.setattr(mobile.qrcode.QRCode, 'add_data', capture)
    response = client.get('/api/v1/install/qr.png')
    assert response.status_code == 200
    assert payloads == ['https://civic-example.onrender.com/install']
    image = Image.open(io.BytesIO(response.content))
    assert image.format == 'PNG' and image.width == image.height and image.width >= 290
    monkeypatch.delenv('RENDER_EXTERNAL_URL')
    assert client.get('/api/v1/install/qr.png').status_code == 409
    assert client.get('/api/v1/install').json()['shareable'] is False


def test_manifest_and_icons_are_self_hosted():
    public = Path(__file__).resolve().parents[1] / 'apps/web/public'
    manifest = json.loads((public / 'manifest.webmanifest').read_text())
    assert manifest['display'] == 'standalone'
    assert manifest['scope'] == '/' and manifest['start_url'].startswith('/')
    for icon in manifest['icons']:
        assert icon['src'].startswith('/icons/')
        img = Image.open(public / icon['src'].lstrip('/'))
        assert f'{img.width}x{img.height}' == icon['sizes']
