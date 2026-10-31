"""Software-only operational visibility and bounded, explicit temporary-data cleanup."""
import hashlib
import json
import os
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, update

from .database import get_db
from .domain import audit
from .models import Configuration, Job, Session, Upload, now
from .security import current_user, require_admin, DEMO_MODE, SECURE_COOKIES

router = APIRouter(prefix='/api/v1/operations')
DEFAULT_POLICY = {'enabled': False, 'expired_session_grace_hours': 24, 'uncommitted_upload_days': 30, 'basis': ''}


def worker_heartbeat(db):
    row = db.get(Configuration, 'worker-heartbeat')
    if row and time.time() - row.value.get('epoch', 0) < 30:
        return
    value = {'at': now(), 'epoch': time.time()}
    if row:
        row.value = value
        row.version += 1
    else:
        db.add(Configuration(key='worker-heartbeat', value=value))
    db.commit()


@router.get('/readiness')
def readiness(user=Depends(current_user), db=Depends(get_db)):
    require_admin(user)
    row = db.get(Configuration, 'worker-heartbeat')
    age = max(0, time.time() - row.value.get('epoch', 0)) if row else None
    policy = db.get(Configuration, 'temporary-retention')
    return {
        'scope': 'Software-only; no hardware required', 'demo_mode': DEMO_MODE,
        'database': 'reachable',
        'worker': {'state': 'not_observed' if age is None else 'recent' if age <= 900 else 'stale',
                   'last_seen': row.value['at'] if row else None, 'age_seconds': round(age) if age is not None else None,
                   'threshold_seconds': 900},
        'jobs': {state: db.query(Job).filter_by(status=state).count() for state in ['queued', 'running', 'paused', 'failed']},
        'secure_cookies': SECURE_COOKIES,
        'email_configured': bool(os.getenv('CIVIC_SMTP_HOST') and os.getenv('CIVIC_SMTP_FROM')),
        'temporary_retention_configured': bool(policy and policy.value.get('enabled')),
        'limitations': ['Worker heartbeat is process activity, not proof of every job succeeding.',
                        'Public hosting, TLS, restore drills and capacity require deployment-specific verification.'],
    }


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Reason(Strict):
    reason: str = Field(min_length=10, max_length=1000)

    @field_validator('reason')
    @classmethod
    def meaningful(cls, value):
        if len(value.strip()) < 10:
            raise ValueError('Explain the change using at least ten characters.')
        return value.strip()


class RetentionPolicy(Reason):
    version: int = Field(ge=0)
    enabled: bool
    expired_session_grace_hours: int = Field(ge=0, le=720)
    uncommitted_upload_days: int = Field(ge=1, le=3650)
    basis: str = Field(min_length=10, max_length=1000)

    @field_validator('basis')
    @classmethod
    def basis_required(cls, value):
        if len(value.strip()) < 10:
            raise ValueError('Record the approved retention basis.')
        return value.strip()


@router.get('/retention')
def retention_policy(user=Depends(current_user), db=Depends(get_db)):
    require_admin(user)
    row = db.get(Configuration, 'temporary-retention')
    return {'version': row.version if row else 0, **(row.value if row else DEFAULT_POLICY)}


@router.post('/retention')
def save_retention(body: RetentionPolicy, user=Depends(current_user), db=Depends(get_db)):
    require_admin(user)
    row = db.get(Configuration, 'temporary-retention')
    value = body.model_dump(exclude={'version', 'reason'})
    if row:
        changed = db.execute(update(Configuration).where(Configuration.key == row.key, Configuration.version == body.version).values(value=value, version=body.version + 1))
        if changed.rowcount != 1:
            raise HTTPException(409, 'Retention policy changed. Refresh before saving.')
    elif body.version == 0:
        db.add(Configuration(key='temporary-retention', value=value))
    else:
        raise HTTPException(409, 'Retention policy changed. Refresh before saving.')
    audit(db, user, None, 'temporary_retention_policy', body.reason, after=value)
    db.commit()
    return retention_policy(user, db)


def candidates(db):
    row = db.get(Configuration, 'temporary-retention')
    if not row or not row.value.get('enabled'):
        raise HTTPException(409, 'Configure and enable an approved temporary-data policy first.')
    cutoff = datetime.now(timezone.utc) - timedelta(days=row.value['uncommitted_upload_days'])
    session_cutoff = time.time() - row.value['expired_session_grace_hours'] * 3600
    sessions = db.query(Session).filter(Session.expires_at < session_cutoff).order_by(Session.token_hash).limit(500).all()
    uploads = db.query(Upload).filter(Upload.status == 'preview', Upload.created_at < cutoff.isoformat()).order_by(Upload.id).limit(500).all()
    fingerprint = hashlib.sha256(json.dumps([row.version, [(s.token_hash, s.expires_at) for s in sessions], [(u.id, u.created_at, u.status) for u in uploads]], sort_keys=True).encode()).hexdigest()
    return row, sessions, uploads, fingerprint, cutoff.isoformat(), session_cutoff


@router.get('/retention/preview')
def retention_preview(user=Depends(current_user), db=Depends(get_db)):
    require_admin(user)
    row, sessions, uploads, fingerprint, cutoff, _ = candidates(db)
    return {'version': row.version, 'confirmation': fingerprint, 'expired_sessions': len(sessions),
            'uncommitted_uploads': len(uploads), 'upload_cutoff': cutoff, 'batch_limit_per_kind': 500,
            'protected': ['complaints', 'cases', 'evidence', 'audit history', 'committed observations', 'accounts']}


class Cleanup(Reason):
    version: int = Field(ge=1)
    confirmation: str = Field(pattern=r'^[a-f0-9]{64}$')


@router.post('/retention/execute')
def retention_execute(body: Cleanup, user=Depends(current_user), db=Depends(get_db)):
    require_admin(user)
    lock = db.execute(update(Configuration).where(Configuration.key == 'temporary-retention', Configuration.version == body.version).values(version=body.version))
    if lock.rowcount != 1:
        raise HTTPException(409, 'Policy changed; preview again.')
    row, sessions, uploads, fingerprint, cutoff, session_cutoff = candidates(db)
    if row.version != body.version or fingerprint != body.confirmation:
        raise HTTPException(409, 'Eligible records changed; preview again before deleting.')
    removed_sessions = db.execute(delete(Session).where(Session.token_hash.in_([s.token_hash for s in sessions]), Session.expires_at < session_cutoff)).rowcount
    removed_uploads = db.execute(delete(Upload).where(Upload.id.in_([u.id for u in uploads]), Upload.status == 'preview', Upload.created_at < cutoff)).rowcount
    if removed_sessions != len(sessions) or removed_uploads != len(uploads):
        db.rollback()
        raise HTTPException(409, 'Records changed; no cleanup committed. Preview again.')
    result = {'expired_sessions': removed_sessions, 'uncommitted_uploads': removed_uploads}
    audit(db, user, None, 'temporary_retention_cleanup', body.reason, after={**result, 'policy_version': row.version})
    db.commit()
    return result
