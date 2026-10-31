"""Asset-bound telemetry. Connectivity and observation freshness are separate signals."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import update

from .database import get_db
from .domain import audit, notify
from .models import Asset, Configuration, Reading, User, now
from .security import DEMO_MODE, current_user, in_scope, rate_limit, require_admin, require_staff

router = APIRouter(prefix="/api/v1/sensors")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Device(Strict):
    asset_id: str
    stale_minutes: int = Field(default=30, ge=1, le=10080)
    offline_minutes: int = Field(default=120, ge=2, le=43200)
    source: Literal["Simulated", "Live"]

    @model_validator(mode="after")
    def thresholds(self):
        if self.offline_minutes <= self.stale_minutes:
            raise ValueError("Offline threshold must exceed stale threshold.")
        return self


@router.post("/register")
def register(body: Device, user=Depends(current_user), db=Depends(get_db)):
    require_admin(user)
    asset = db.get(Asset, body.asset_id)
    if not asset or asset.domain != "water":
        raise HTTPException(422, "Choose a registered water asset.")
    if (DEMO_MODE and body.source != "Simulated") or (not DEMO_MODE and body.source != "Live") or (body.source == "Live" and asset.provenance in {"Synthetic", "Simulated"}):
        raise HTTPException(422, "Keep simulator devices in demo mode and live devices on operational assets in non-demo mode.")
    key = "sensor:" + asset.id
    if db.get(Configuration, key):
        raise HTTPException(409, "Device already registered. Use the rotation endpoint to replace credentials.")
    token = secrets.token_urlsafe(32)
    value = {**body.model_dump(), "token_hash": hashlib.sha256(token.encode()).hexdigest(), "registered_at": now(), "last_contact": None, "state": "offline", "state_at": now(), "recovered_at": None, "active": True}
    db.add(Configuration(key=key, value=value))
    audit(db, user, None, "sensor_registered", "Asset-bound ingestion credential created", after={"asset_id": asset.id, "source": body.source})
    db.commit()
    return {"asset_id": asset.id, "token": token, "notice": "Store securely; this credential is shown only once."}


class DeviceUpdate(Device):
    version: int = Field(ge=1)
    active: bool = True


@router.post("/configure")
def configure(body: DeviceUpdate, user=Depends(current_user), db=Depends(get_db)):
    require_admin(user)
    row = db.get(Configuration, "sensor:" + body.asset_id)
    if not row or row.value["source"] != body.source:
        raise HTTPException(422, "Registered source cannot be changed.")
    value = {**row.value, "stale_minutes": body.stale_minutes, "offline_minutes": body.offline_minutes, "active": body.active}
    result = db.execute(update(Configuration).where(Configuration.key == row.key, Configuration.version == body.version).values(value=value, version=body.version + 1))
    if result.rowcount != 1:
        raise HTTPException(409, "Device changed; refresh.")
    audit(db, user, None, "sensor_configuration", "Thresholds or active state changed", after=body.model_dump())
    db.commit()
    return {"version": body.version + 1}


@router.post("/{asset_id}/rotate")
def rotate(asset_id: str, user=Depends(current_user), db=Depends(get_db)):
    require_admin(user)
    row = db.get(Configuration, "sensor:" + asset_id)
    if not row:
        raise HTTPException(404, "Device not registered.")
    token = secrets.token_urlsafe(32)
    changed = db.execute(update(Configuration).where(Configuration.key == row.key, Configuration.version == row.version).values(value={**row.value, "token_hash": hashlib.sha256(token.encode()).hexdigest()}, version=row.version + 1))
    if changed.rowcount != 1:
        raise HTTPException(409, "Device changed; refresh.")
    audit(db, user, None, "sensor_key_rotated", "Old device credential revoked", after={"asset_id": asset_id})
    db.commit()
    return {"token": token}


class Observation(Strict):
    id: str = Field(min_length=8, max_length=100)
    timestamp: datetime
    interval_minutes: float = Field(gt=0, le=1440, allow_inf_nan=False)
    quantity: float | None = Field(default=None, ge=0, le=1e12, allow_inf_nan=False)
    unit: Literal["L", "m3"]
    quality: Literal["valid", "missing", "invalid"] = "valid"

    @field_validator("timestamp")
    @classmethod
    def utc(cls, value):
        if value.tzinfo is None:
            raise ValueError("Timestamp requires an explicit timezone.")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def quality_value(self):
        if self.quality == "valid" and self.quantity is None:
            raise ValueError("A valid reading needs a measurement.")
        if self.quality == "missing" and self.quantity is not None:
            raise ValueError("Missing measurements must remain null.")
        return self


class Packet(Strict):
    readings: list[Observation] = Field(default_factory=list, max_length=100)


def sensor_state(value, at):
    if not value.get("active", True):
        return "disabled"
    if not value.get("last_contact"):
        return "offline"
    age = (at - datetime.fromisoformat(value["last_contact"])).total_seconds() / 60
    return "offline" if age >= value["offline_minutes"] else "stale" if age >= value["stale_minutes"] else "reporting"


def record_state(db, row, value, at):
    state = sensor_state(value, at)
    previous = value.get("state", "offline")
    if state != previous:
        value = {**value, "state": state, "state_at": at.isoformat()}
        if state == "reporting" and previous in {"stale", "offline"}:
            value["recovered_at"] = at.isoformat()
        audit(db, None, None, "sensor_state", "Device contact state changed; not a leakage diagnosis", before={"state": previous}, after={"asset_id": value["asset_id"], "state": state, "at": at.isoformat()})
        asset = db.get(Asset, value["asset_id"])
        for user in db.query(User).filter(User.active.is_(True), User.role.in_(["admin", "operator"])).all():
            if in_scope(user, "water", asset.zone_id):
                notify(db, user.id, None, f"Water sensor {asset.id}: {state}", f"sensor:{asset.id}:{row.version}:{state}")
    return value


@router.post("/{asset_id}/readings")
def ingest(asset_id: str, body: Packet, authorization: str = Header(default=""), db=Depends(get_db)):
    row = db.get(Configuration, "sensor:" + asset_id)
    token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
    if not row or not row.value.get("active") or not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), row.value["token_hash"]):
        raise HTTPException(401, "Invalid device credential.")
    rate_limit("sensor:" + asset_id, 120, 60)
    asset = db.get(Asset, asset_id)
    at = datetime.now(timezone.utc)
    # Acquire a versioned write before checking duplicates; concurrent packets retry safely.
    claimed = db.execute(update(Configuration).where(Configuration.key == row.key, Configuration.version == row.version).values(version=row.version + 1), execution_options={"synchronize_session": False})
    if claimed.rowcount != 1:
        raise HTTPException(409, "Concurrent packet; retry the same readings.")
    inserted = duplicates = delayed = 0
    for reading in body.readings:
        end = reading.timestamp + timedelta(minutes=reading.interval_minutes)
        if end > at + timedelta(minutes=5):
            raise HTTPException(422, "Future intervals exceed the five-minute clock tolerance.")
        quantity = reading.quantity * (1000 if reading.unit == "m3" else 1) if reading.quantity is not None else None
        expected = {"asset_id": asset.id, "timestamp": reading.timestamp.isoformat(), "interval_minutes": reading.interval_minutes, "quantity": quantity, "unit": "L", "quality_flag": reading.quality, "source": row.value["source"]}
        prior = db.get(Reading, reading.id) or db.query(Reading).filter_by(asset_id=asset.id, timestamp=expected["timestamp"]).first()
        if prior:
            if any(getattr(prior, k) != v for k, v in expected.items()):
                raise HTTPException(409, "Reading identity conflicts with stored content.")
            duplicates += 1
            continue
        for existing in db.query(Reading).filter_by(asset_id=asset.id).all():
            start = datetime.fromisoformat(existing.timestamp.replace("Z", "+00:00"))
            if reading.timestamp < start + timedelta(minutes=existing.interval_minutes) and end > start:
                raise HTTPException(409, "Overlapping measurement interval.")
        delayed += int((at - end).total_seconds() > row.value["stale_minutes"] * 60)
        db.add(Reading(id=reading.id, zone_id=asset.zone_id, domain="water", **expected, original={"received_at": at.isoformat(), "input_unit": reading.unit, "input_quantity": reading.quantity, "provenance": row.value["source"]}))
        db.flush()
        inserted += 1
    row.value = record_state(db, row, {**row.value, "last_contact": at.isoformat()}, at)
    audit(db, None, None, "sensor_packet", "Authenticated packet accepted", after={"asset_id": asset.id, "inserted": inserted, "duplicates": duplicates, "delayed": delayed})
    db.commit()
    return {"accepted": inserted, "duplicates": duplicates, "delayed": delayed, "source": row.value["source"], "received_at": at.isoformat()}


def monitor_sensors(db):
    at = datetime.now(timezone.utc)
    for row in db.query(Configuration).filter(Configuration.key.startswith("sensor:")).all():
        value = record_state(db, row, dict(row.value), at)
        if value != row.value:
            changed = db.execute(update(Configuration).where(Configuration.key == row.key, Configuration.version == row.version).values(value=value, version=row.version + 1))
            if changed.rowcount != 1:
                db.rollback()
                return


@router.get("")
def devices(user=Depends(current_user), db=Depends(get_db)):
    require_staff(user)
    result = []
    at = datetime.now(timezone.utc)
    for row in db.query(Configuration).filter(Configuration.key.startswith("sensor:")).all():
        asset = db.get(Asset, row.value["asset_id"])
        if not asset or not in_scope(user, asset.domain, asset.zone_id):
            continue
        reading = db.query(Reading).filter_by(asset_id=asset.id, source=row.value["source"]).order_by(Reading.timestamp.desc()).first()
        last_end = (datetime.fromisoformat(reading.timestamp) + timedelta(minutes=reading.interval_minutes)) if reading else None
        result.append({**{k: v for k, v in row.value.items() if k != "token_hash"}, "version": row.version, "state": sensor_state(row.value, at), "latest_observation": reading.timestamp if reading else None, "latest_quality": reading.quality_flag if reading else "missing", "observation_stale": not last_end or (at - last_end).total_seconds() > row.value["stale_minutes"] * 60})
    return result
