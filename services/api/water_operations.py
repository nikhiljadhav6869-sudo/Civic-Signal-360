"""Versioned, zone-scoped water operations with explicit accounting boundaries."""
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import update

from .database import get_db
from .domain import audit
from .models import Asset, Configuration, Reading, Zone
from .security import current_user, in_scope, require_admin, require_staff
from services.analytics.water_operations import instant, schedule_review, water_balance

router = APIRouter(prefix="/api/v1/water")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Window(Strict):
    days: list[int] = Field(min_length=1, max_length=7)
    start_minute: int = Field(ge=0, le=1439)
    end_minute: int = Field(ge=0, le=1440)
    label: str = Field(min_length=3, max_length=120)

    @model_validator(mode="after")
    def valid_window(self):
        if len(set(self.days)) != len(self.days) or any(d < 0 or d > 6 for d in self.days):
            raise ValueError("Days must be unique Monday=0 through Sunday=6.")
        if self.start_minute == self.end_minute:
            raise ValueError("Use 00:00–24:00 for an all-day window.")
        return self


class WaterConfiguration(Strict):
    version: int = Field(ge=0)
    timezone: Literal["Asia/Kolkata", "UTC"] = "Asia/Kolkata"
    supply_windows: list[Window] = Field(default_factory=list, max_length=21)
    exceptions: list[Window] = Field(default_factory=list, max_length=21)
    outside_rate_lph: float = Field(default=0, ge=0, le=1e9, allow_inf_nan=False)
    inlet_ids: list[str] = Field(default_factory=list, max_length=100)
    outlet_ids: list[str] = Field(default_factory=list, max_length=100)
    consumption_ids: list[str] = Field(default_factory=list, max_length=100)
    meter_parents: dict[str, str] = Field(default_factory=dict, max_length=200)
    boundary_confirmed: bool = False
    reason: str = Field(min_length=5, max_length=2000)

    @model_validator(mode="after")
    def hierarchy(self):
        selected = self.inlet_ids + self.outlet_ids + self.consumption_ids
        if len(selected) != len(set(selected)):
            raise ValueError("Each meter may appear in one accounting role only.")
        for child in self.meter_parents:
            seen, node = {child}, child
            while node in self.meter_parents:
                node = self.meter_parents[node]
                if node in seen:
                    raise ValueError("Meter hierarchy must not contain cycles.")
                seen.add(node)
        # An inlet may be the ancestor of downstream consumption. Inside a summed
        # role, or between the two deducted roles, ancestors would double count.
        for group in (self.inlet_ids, self.outlet_ids + self.consumption_ids):
            for child in group:
                node = child
                while node in self.meter_parents:
                    node = self.meter_parents[node]
                    if node in group:
                        raise ValueError("Do not sum parent and child meters in the same accounting side.")
        if self.boundary_confirmed and not self.inlet_ids:
            raise ValueError("A confirmed boundary requires an inlet meter.")
        return self


def access(db, user, zone_id):
    require_staff(user)
    if not in_scope(user, "water", zone_id) or not db.get(Zone, zone_id):
        raise HTTPException(404, "Water service zone not available.")


def saved(db, zone_id):
    row = db.get(Configuration, "water-operations:" + zone_id)
    return {"version": row.version, **row.value} if row else WaterConfiguration(version=0, reason="Not configured").model_dump(exclude={"reason"})


@router.get("/zones/{zone_id}/operations")
def get_operations(zone_id: str, user=Depends(current_user), db=Depends(get_db)):
    access(db, user, zone_id)
    assets = db.query(Asset).filter_by(zone_id=zone_id, domain="water").all()
    ids = [a.id for a in assets]
    latest = db.query(Reading).filter(Reading.asset_id.in_(ids), Reading.domain == "water").order_by(Reading.timestamp.desc()).first()
    end = (instant(latest.timestamp) + timedelta(minutes=latest.interval_minutes)).isoformat() if latest else None
    return {"zone_id": zone_id, "configuration": saved(db, zone_id), "assets": [{"id": a.id, "name": a.name, "kind": a.kind, "provenance": a.provenance} for a in assets], "latest_end": end}


@router.put("/zones/{zone_id}/operations")
def save_operations(zone_id: str, body: WaterConfiguration, user=Depends(current_user), db=Depends(get_db)):
    require_admin(user)
    access(db, user, zone_id)
    ids = set(body.inlet_ids + body.outlet_ids + body.consumption_ids + list(body.meter_parents) + list(body.meter_parents.values()))
    for ident in ids:
        asset = db.get(Asset, ident)
        if not asset or asset.domain != "water" or asset.zone_id != zone_id or "meter" not in asset.kind.lower():
            raise HTTPException(422, "Use registered water meters in this service zone.")
    key = "water-operations:" + zone_id
    previous = db.get(Configuration, key)
    value = body.model_dump(exclude={"reason", "version"})
    before = saved(db, zone_id)
    if previous is None:
        if body.version != 0:
            raise HTTPException(409, "Configuration changed. Reload before saving.")
        db.add(Configuration(key=key, value=value, version=1))
    else:
        changed = db.execute(update(Configuration).where(Configuration.key == key, Configuration.version == body.version).values(value=value, version=body.version+1))
        if changed.rowcount != 1:
            raise HTTPException(409, "Configuration changed. Reload before saving.")
    audit(db, user, None, "water_operations_configured", body.reason, before=before, after={"zone_id": zone_id, "version": body.version+1, **value})
    db.commit()
    return saved(db, zone_id)


class ReviewInput(Strict):
    start: datetime
    end: datetime
    configuration_version: int = Field(ge=0)
    storage_change_l: float | None = Field(default=None, allow_inf_nan=False, ge=-1e12, le=1e12)
    authorized_unmetered_l: float | None = Field(default=None, allow_inf_nan=False, ge=0, le=1e12)
    accounting_note: str = Field(default="", max_length=2000)

    @field_validator("start", "end")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("Every timestamp must include a timezone.")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def window(self):
        if not timedelta(0) < self.end-self.start <= timedelta(days=31):
            raise ValueError("Choose an ordered window of at most 31 days.")
        if (self.storage_change_l is not None or self.authorized_unmetered_l is not None) and len(self.accounting_note.strip()) < 5:
            raise ValueError("Explain the source of supplied storage and authorized-use values.")
        return self


@router.post("/zones/{zone_id}/review")
def review_operations(zone_id: str, body: ReviewInput, user=Depends(current_user), db=Depends(get_db)):
    access(db, user, zone_id)
    config = saved(db, zone_id)
    if body.configuration_version != config["version"]:
        raise HTTPException(409, "Configuration changed. Reload it before reviewing observations.")
    assets = db.query(Asset).filter_by(zone_id=zone_id, domain="water").all()
    meter_ids = [a.id for a in assets if "meter" in a.kind.lower()]
    # Query with a one-day margin; valid input intervals cannot exceed one day.
    readings = db.query(Reading).filter(Reading.asset_id.in_(meter_ids), Reading.domain == "water", Reading.timestamp >= (body.start-timedelta(days=1)).isoformat(), Reading.timestamp < body.end.isoformat()).all()
    rows = [{key: getattr(r, key) for key in ("id", "asset_id", "timestamp", "interval_minutes", "quantity", "unit", "source", "quality_flag")} for r in readings]
    selected = [r for r in rows if instant(r["timestamp"]) >= body.start]
    schedule = schedule_review(selected, config)
    balance = water_balance(rows, config, body.start, body.end, body.storage_change_l, body.authorized_unmetered_l)
    return {"zone_id": zone_id, "configuration_version": config["version"], "window": {"start": body.start.isoformat(), "end_exclusive": body.end.isoformat()}, "schedule": schedule,
            "schedule_counts": {state: sum(r["status"] == state for r in schedule) for state in sorted({r["status"] for r in schedule})},
            "balance": balance, "accounting_input_provenance": "User-supplied; not independently verified", "accounting_note": body.accounting_note,
            "configuration_snapshot": config, "requires_human_review": True}
