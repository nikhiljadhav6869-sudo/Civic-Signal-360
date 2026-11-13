"""Public installation metadata and local QR generation, without account data."""
import io
import ipaddress
import os
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
import qrcode

router = APIRouter(prefix='/api/v1/install', tags=['mobile install'])


def install_url():
    # Never trust a request Host header to publish a QR destination.
    value = os.getenv('CIVIC_PUBLIC_ORIGIN') or os.getenv('RENDER_EXTERNAL_URL', '')
    try:
        parts = urlsplit(value)
        host = parts.hostname or ''
        if parts.scheme != 'https' or not host or parts.username or parts.password or parts.port not in (None, 443) or parts.path not in ('', '/') or parts.query or parts.fragment:
            return None
        if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal', '.invalid', '.test')) or '.' not in host:
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            pass
        return value.rstrip('/') + '/install'
    except ValueError:
        return None


@router.get('')
def installation():
    url = install_url()
    return {'url': url, 'shareable': bool(url), 'kind': 'web_app', 'store_download_available': False}


@router.get('/qr.png')
def installation_qr():
    url = install_url()
    if not url:
        raise HTTPException(409, 'The public HTTPS installation address has not been configured.')
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    code.add_data(url)
    code.make(fit=True)
    output = io.BytesIO()
    code.make_image(fill_color='black', back_color='white').save(output, format='PNG')
    return Response(output.getvalue(), media_type='image/png', headers={
        'Content-Disposition': 'inline; filename="CivicSignal-360-install-QR.png"',
        'Cache-Control': 'no-store',
    })
