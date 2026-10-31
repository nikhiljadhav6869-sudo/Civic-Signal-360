"""Private complaint follow-through; explicit public messages never expose staff notes."""
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import update

from .database import get_db
from .domain import audit, case_access, mutate_case, visible_cases
from .models import Audit, Case, Configuration, Evidence, Report, User, now, uid
from .security import current_user, in_scope, require_admin, require_staff

router = APIRouter(prefix="/api/v1")
NEXT = {"needs_review": "acknowledge", "investigating": "assign", "assigned": "inspect", "intervention": "monitor", "monitoring": "follow_up", "resolved": "review_outcome", "closed": "challenge_if_needed"}


def service_target(db, case):
    row = db.get(Configuration, "response-policy")
    policies = row.value.get("rules", []) if row else []
    return next((r for r in policies if r["domain"] == case.domain and r["severity"] == case.severity), None)


def apply_target(db, case):
    rule = service_target(db, case)
    case.deadline_at = (datetime.now(timezone.utc) + timedelta(hours=rule["hours"])).isoformat() if rule else None
    case.evidence = {**case.evidence, "service_target": rule}


def accountability(db, case):
    public = (case.evidence or {}).get("public_update", {})
    policy = (case.evidence or {}).get("service_target")
    due = public.get("next_update_at") or (case.deadline_at if policy else None)
    owner = db.get(User, case.assigned_to) if case.assigned_to else None
    assigned = bool(owner and owner.active and owner.role == 'inspector' and in_scope(owner, case.domain, case.zone_id))
    next_step = NEXT.get(case.status, 'review')
    if not assigned and case.status in {'assigned', 'investigating', 'intervention', 'monitoring'}:
        next_step = 'assign'
    elif assigned and case.status == 'investigating':
        next_step = 'inspect'
    return {"team": policy["team"] if policy else case.domain, "assignment": "assigned" if assigned else "unassigned", "next_action": next_step, "next_update_at": due, "overdue": bool(due and due < now() and case.status not in {"resolved", "closed"}), "target_basis": policy["basis"] if policy else None, "public_update": public.get("message"), "public_update_at": public.get("at"), "resolution": (case.evidence or {}).get("public_resolution"), "version": case.version}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Explanation(Strict):
    reason: str = Field(min_length=10, max_length=2000)

    @field_validator("reason")
    @classmethod
    def meaningful(cls, value):
        if len(value.strip()) < 10:
            raise ValueError("Enter at least ten non-padding characters.")
        return value.strip()


class Dispute(Explanation):
    version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=100)


@router.post("/reports/{report_id}/dispute")
def dispute(report_id: str, body: Dispute, user=Depends(current_user), db=Depends(get_db)):
    report = db.get(Report, report_id)
    if not report or report.user_id != user.id:
        raise HTTPException(404, "Report not found.")
    case = db.get(Case, report.case_id)
    prior = db.query(Evidence).filter_by(case_id=case.id, actor_id=user.id, idempotency_key=body.idempotency_key).first()
    if prior:
        if prior.kind != "citizen_dispute" or prior.notes != body.reason:
            raise HTTPException(409, "Submission key already used for different content.")
        return {"status": case.status, "duplicate": True, "version": case.version}
    if case.status not in {"resolved", "closed"}:
        raise HTTPException(409, "Only a resolved or closed outcome can be challenged. The case may already be reopened.")
    evidence = {**case.evidence}
    evidence.pop("public_resolution", None)
    evidence.pop("public_update", None)
    evidence.pop("field_finding", None)
    target = service_target(db, case)
    evidence["service_target"] = target
    deadline = (datetime.now(timezone.utc) + timedelta(hours=target["hours"])).isoformat() if target else None
    record = Evidence(id=uid(), case_id=case.id, actor_id=user.id, kind="citizen_dispute", notes=body.reason, idempotency_key=body.idempotency_key)
    mutate_case(db, user, case, body.version, "citizen_dispute", body.reason, status="investigating", evidence=evidence, deadline_at=deadline, evidence_ids=[record.id])
    db.add(record)
    db.commit()
    return {"status": case.status, "duplicate": False, "version": case.version}


class PublicUpdate(Explanation):
    version: int = Field(ge=1)
    next_update_at: datetime | None = None

    @field_validator("next_update_at")
    @classmethod
    def zoned(cls, value):
        if value and value.tzinfo is None:
            raise ValueError("A timezone is required.")
        return value.astimezone(timezone.utc) if value else None


@router.post("/cases/{case_id}/public-update")
def public_update(case_id: str, body: PublicUpdate, user=Depends(current_user), db=Depends(get_db)):
    require_staff(user)
    case = case_access(db, user, case_id)
    if body.next_update_at and body.next_update_at <= datetime.now(timezone.utc):
        raise HTTPException(422, "Choose a future next-update time.")
    # A message-only update does not silently withdraw an explicitly recorded
    # target. Do not infer a public commitment from a legacy internal deadline.
    previous_due = (case.evidence or {}).get("public_update", {}).get("next_update_at")
    message = {"message": body.reason, "at": now(), "next_update_at": body.next_update_at.isoformat() if body.next_update_at else previous_due}
    mutate_case(db, user, case, body.version, "public_update", "Explicit citizen-facing update", evidence={**case.evidence, "public_update": message}, deadline_at=message["next_update_at"] or case.deadline_at, audit_after={"public_message": body.reason})
    db.commit()
    return accountability(db, case)


class Outcome(Explanation):
    version: int = Field(ge=1)
    finding: Literal["confirmed_leak", "false_alert", "inconclusive", "other_verified_issue"]
    evidence_id: str


@router.post("/cases/{case_id}/finding")
def record_finding(case_id: str, body: Outcome, user=Depends(current_user), db=Depends(get_db)):
    case = case_access(db, user, case_id)
    if user.role not in {"admin", "inspector"} or case.status in {"closed", "resolved"}:
        raise HTTPException(403, "An authorized field worker must classify an open investigation.")
    record = db.get(Evidence, body.evidence_id)
    if not record or record.case_id != case.id or record.kind != "inspection":
        raise HTTPException(422, "Link an inspection from this case.")
    reopened = db.query(Audit).filter(Audit.case_id == case.id, Audit.action.in_(["citizen_dispute", "transition"])).order_by(Audit.created_at.desc()).all()
    latest_reopen = next((a for a in reopened if a.action == "citizen_dispute" or (a.before.get("status") in {"closed", "resolved"} and a.after.get("status") == "investigating")), None)
    if latest_reopen and record.created_at <= latest_reopen.created_at:
        raise HTTPException(422, "Record a new inspection after reopening.")
    if body.finding != "inconclusive" and not record.checklist.get("site_verified"):
        raise HTTPException(422, "A definitive finding requires site verification on its inspection.")
    if body.finding == "confirmed_leak" and (case.domain != "water" or not record.checklist.get("site_verified")):
        raise HTTPException(422, "Confirm site verification on a water inspection first.")
    finding = {"classification": body.finding, "reason": body.reason, "inspection_id": record.id, "at": now(), "actor_id": user.id, "provenance": "Manual field record; not independently verified"}
    mutate_case(db, user, case, body.version, "field_classification", body.reason, evidence={**case.evidence, "field_finding": finding})
    db.commit()
    return finding


class PolicyRule(Strict):
    domain: Literal["water", "electricity", "roads", "drainage", "waste", "streetlights", "general"]
    severity: Literal["low", "medium", "high", "critical", "warning"]
    hours: int = Field(ge=1, le=8760)
    team: str = Field(min_length=3, max_length=100)
    supervisor_id: str
    basis: str = Field(min_length=10, max_length=500)


class Policy(Explanation):
    version: int = Field(ge=0)
    rules: list[PolicyRule] = Field(max_length=35)


@router.get("/operations/policy")
def get_policy(user=Depends(current_user), db=Depends(get_db)):
    require_admin(user)
    row = db.get(Configuration, "response-policy")
    return {"version": row.version if row else 0, "rules": row.value["rules"] if row else []}


@router.post("/operations/policy")
def save_policy(body: Policy, user=Depends(current_user), db=Depends(get_db)):
    require_admin(user)
    if len({(r.domain, r.severity) for r in body.rules}) != len(body.rules):
        raise HTTPException(422, "One target per complaint domain and severity.")
    for rule in body.rules:
        supervisor = db.get(User, rule.supervisor_id)
        if not supervisor or not supervisor.active or supervisor.role not in {"operator", "admin"} or (supervisor.role != "admin" and (rule.domain not in supervisor.domains or not supervisor.zones)):
            raise HTTPException(422, "Choose an active supervisor authorized for this domain.")
    value = {"rules": [r.model_dump() for r in body.rules]}
    row = db.get(Configuration, "response-policy")
    if row:
        changed = db.execute(update(Configuration).where(Configuration.key == row.key, Configuration.version == body.version).values(value=value, version=body.version + 1))
        if changed.rowcount != 1:
            raise HTTPException(409, "Policy changed; reload before editing.")
    elif body.version == 0:
        db.add(Configuration(key="response-policy", value=value))
    else:
        raise HTTPException(409, "Policy changed; reload before editing.")
    audit(db, user, None, "response_policy", body.reason, after=value)
    db.commit()
    return get_policy(user, db)


@router.get("/operations/queue")
def queue(user=Depends(current_user), db=Depends(get_db)):
    if user.role == "citizen":
        raise HTTPException(403, "Staff access required.")
    rows = []
    for c in visible_cases(db, user):
        if c.status in {'closed', 'resolved'}:
            continue
        context = accountability(db, c)
        rows.append({"id": c.id, "title": c.title, "domain": c.domain, "status": c.status, "severity": c.severity, "provenance": c.provenance, "updated_at": c.updated_at, "assigned_to": c.assigned_to if context['assignment'] == 'assigned' else None, **context})
    return rows
