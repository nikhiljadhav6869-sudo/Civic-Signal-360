"""Opt-in email outbox with durable attempts. No provider configuration means no delivery claim."""
import os
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import update

from .database import get_db
from .models import Configuration, Notification, User, now
from .security import current_user

router = APIRouter(prefix="/api/v1/delivery")


def enqueue(db, notification):
    user = db.get(User, notification.user_id)
    if not user or not (user.settings or {}).get("email_updates"):
        return
    db.flush()
    key = "delivery:" + notification.id
    if not db.get(Configuration, key):
        db.add(Configuration(key=key, value={"user_id": user.id, "notification_id": notification.id, "state": "queued", "attempts": [], "retry_at": now()}))


def smtp_send(user, ident):
    host, sender = os.getenv("CIVIC_SMTP_HOST"), os.getenv("CIVIC_SMTP_FROM")
    if not host or not sender:
        raise RuntimeError("provider_not_configured")
    message = EmailMessage()
    message["From"], message["To"] = sender, user.email
    message["Subject"] = "CivicSignal 360 — Update / अद्ययावत माहिती"
    message["Message-ID"] = f"<{ident}@civicsignal.local>"
    message.set_content("A private update is available in your CivicSignal 360 account. Sign in to review it.\nआपल्या CivicSignal 360 खात्यात नवीन माहिती उपलब्ध आहे. ती पाहण्यासाठी प्रवेश करा.\nThis message does not confirm a repair. / हा संदेश दुरुस्तीची पुष्टी करत नाही.")
    with smtplib.SMTP(host, int(os.getenv("CIVIC_SMTP_PORT", "587")), timeout=10) as client:
        client.starttls(context=ssl.create_default_context())
        if os.getenv("CIVIC_SMTP_USER"):
            client.login(os.environ["CIVIC_SMTP_USER"], os.environ["CIVIC_SMTP_PASSWORD"])
        refused = client.send_message(message)
        if refused:
            raise RuntimeError("provider_rejected")


def process_delivery(db, transport=smtp_send):
    # One bounded attempt per worker pass. The lease permits recovery after a crash.
    for row in db.query(Configuration).filter(Configuration.key.startswith("delivery:")).all():
        value = dict(row.value)
        if value["state"] not in {"queued", "sending"} or value["retry_at"] > now():
            continue
        lease = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        claimed = {**value, "state": "sending", "retry_at": lease}
        version = row.version
        changed = db.execute(update(Configuration).where(Configuration.key == row.key, Configuration.version == version).values(value=claimed, version=version + 1))
        if changed.rowcount != 1:
            db.rollback()
            return
        db.commit()
        user = db.get(User, value["user_id"])
        outcome = "provider_accepted"
        if not user or not user.active or not user.settings.get("email_updates"):
            outcome = "disabled"
        else:
            try:
                transport(user, value["notification_id"])
            except Exception:
                # Provider exceptions can contain addresses, credentials or server details.
                outcome = "failed"
        attempts = [*value["attempts"], {"at": now(), "outcome": outcome}]
        state = "queued" if outcome == "failed" and len(attempts) < 3 else outcome
        final = {**value, "state": state, "attempts": attempts, "retry_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()}
        db.execute(update(Configuration).where(Configuration.key == row.key, Configuration.version == version + 1).values(value=final, version=version + 2))
        db.commit()
        return


class Preference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


@router.post("/preference")
def preference(body: Preference, user=Depends(current_user), db=Depends(get_db)):
    user.settings = {**user.settings, "email_updates": body.enabled}
    db.commit()
    return {"enabled": body.enabled}


@router.get("")
def history(user=Depends(current_user), db=Depends(get_db)):
    from .security import can_case
    from .models import Case, Report
    result = []
    for row in db.query(Configuration).filter(Configuration.key.startswith("delivery:")).all():
        if row.value["user_id"] != user.id:
            continue
        notification = db.get(Notification, row.value["notification_id"])
        case = db.get(Case, notification.case_id) if notification and notification.case_id else None
        if case and not (can_case(user, case) or db.query(Report).filter_by(case_id=case.id, user_id=user.id).first()):
            continue
        result.append({"id": row.key.removeprefix("delivery:"), **row.value})
    return {"enabled": bool(user.settings.get("email_updates")), "provider_configured": bool(os.getenv("CIVIC_SMTP_HOST") and os.getenv("CIVIC_SMTP_FROM")), "deliveries": result}


@router.post("/{notification_id}/retry")
def retry(notification_id: str, user=Depends(current_user), db=Depends(get_db)):
    row = db.get(Configuration, "delivery:" + notification_id)
    if not row or row.value["user_id"] != user.id:
        raise HTTPException(404, "Delivery not found.")
    if row.value["state"] != "failed" or not user.settings.get("email_updates"):
        raise HTTPException(409, "Retry requires an opted-in account and a failed delivery.")
    changed = db.execute(update(Configuration).where(Configuration.key == row.key, Configuration.version == row.version).values(value={**row.value, "state": "queued", "retry_at": now()}, version=row.version + 1))
    if changed.rowcount != 1:
        raise HTTPException(409, "Delivery changed; refresh.")
    db.commit()
    return {"state": "queued"}
