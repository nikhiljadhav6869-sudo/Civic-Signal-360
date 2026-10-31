import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from services.api.database import SessionLocal
from services.api.domain import notify_overdue
from services.api.main import app
from services.api.models import Audit, Case, Configuration, Evidence, Notification


def report(client):
    body = {"domain": "water", "zone_id": "river", "title": "Pilot water observation", "description": "Synthetic observation for the accountable pilot.", "location": "Synthetic public test point", "idempotency_key": uuid.uuid4().hex}
    response = client.post('/api/v1/reports', json=body)
    assert response.status_code == 201, response.text
    assert client.post('/api/v1/reports', json=body).json()['id'] == response.json()['id']
    return response.json()


def act(client, ident, path, **body):
    case = client.get('/api/v1/cases/' + ident).json()
    response = client.post('/api/v1/cases/' + ident + '/' + path, json={"version": case['version'], **body})
    assert response.status_code == 200, response.text
    return response.json()


def closed_false_alert(login):
    citizen, operator, inspector = login('citizen'), login('operator'), login('inspector')
    receipt = report(citizen); ident = receipt['case_id']
    act(operator, ident, 'assign', inspector_id='demo-inspector', reason='Inspect the suspected water issue')
    details = act(inspector, ident, 'inspection', notes='Site examination found planned tank filling, no leak.', checklist={'site_verified': True})
    inspection = next(e['id'] for e in details['evidence_records'] if e['kind'] == 'inspection')
    act(inspector, ident, 'finding', finding='false_alert', evidence_id=inspection, reason='Supply schedule and site inspection disprove the leak hypothesis.')
    details = act(operator, ident, 'transition', status='closed', reason='INTERNAL_NOTE_DO_NOT_PUBLISH', public_summary='Inspection found planned tank filling. No leak was observed. Challenge if the issue persists.')
    return citizen, operator, inspector, receipt, details


def test_closure_requires_evidence_and_public_explanation(login):
    citizen, operator = login('citizen'), login('operator')
    receipt = report(citizen)
    ident = receipt['case_id']; case = operator.get('/api/v1/cases/' + ident).json()
    blocked = operator.post('/api/v1/cases/' + ident + '/transition', json={'version':case['version'],'status':'closed','reason':'Dismiss without inspection','public_summary':'Unsupported dismissal must fail.'})
    assert blocked.status_code == 409
    assert citizen.get('/api/v1/reports/'+receipt['id']).json()['status']=='needs_review'
    assert receipt['receipt']=='CS360-'+receipt['id'].upper()


def test_revoked_field_assignment_returns_to_explicit_unassigned_queue(login):
    from services.api.models import User
    citizen, operator=login('citizen'),login('operator')
    receipt=report(citizen);ident=receipt['case_id']
    act(operator,ident,'assign',inspector_id='demo-inspector',reason='Assign an authorized inspector for this observation')
    with SessionLocal() as db:
        user=db.get(User,'demo-inspector');old=user.active;user.active=False;db.commit()
    try:
        row=next(r for r in operator.get('/api/v1/operations/queue').json() if r['id']==ident)
        assert row['assignment']=='unassigned' and row['assigned_to'] is None and row['next_action']=='assign'
        assert citizen.get('/api/v1/reports/'+receipt['id']).json()['accountability']['assignment']=='unassigned'
    finally:
        with SessionLocal() as db:db.get(User,'demo-inspector').active=old;db.commit()


def test_private_dispute_reopens_once_and_old_inspection_cannot_reclose(login):
    citizen, operator, inspector, receipt, closed = closed_false_alert(login)
    tracking = citizen.get('/api/v1/reports/'+receipt['id']).json()
    assert 'INTERNAL_NOTE_DO_NOT_PUBLISH' not in str(tracking)
    assert 'planned tank filling' in tracking['accountability']['resolution']['message']
    second = TestClient(app)
    email=uuid.uuid4().hex+'@example.test'
    result=second.post('/api/v1/auth/register',json={'name':'Another citizen','email':email,'password':'AnotherStrong!2026'})
    second.headers['X-CSRF-Token']=result.json()['csrf_token']
    body={'version':closed['version'],'reason':'Water is still collecting at the same location.','idempotency_key':uuid.uuid4().hex}
    path='/api/v1/reports/'+receipt['id']+'/dispute'
    assert second.post(path,json=body).status_code==404
    assert second.get('/api/v1/reports/'+receipt['id']).status_code==403
    assert citizen.post(path,json=body).json()['status']=='investigating'
    assert citizen.post(path,json=body).json()['duplicate'] is True
    assert citizen.post(path,json={**body,'reason':'Different explanation with same identifier'}).status_code==409
    current=operator.get('/api/v1/cases/'+closed['id']).json()
    assert 'field_finding' not in current['evidence']
    inspection=next(e['id'] for e in current['evidence_records'] if e['kind']=='inspection')
    assert inspector.post('/api/v1/cases/'+closed['id']+'/finding',json={'version':current['version'],'reason':'Reuse old inspection after citizen dispute','finding':'false_alert','evidence_id':inspection}).status_code==422
    assert citizen.get('/api/v1/reports/'+receipt['id']).json()['accountability']['resolution'] is None
    with SessionLocal() as db:
        assert db.query(Evidence).filter_by(case_id=closed['id'],kind='citizen_dispute').count()==1


def test_water_pilot_inspection_intervention_followup_and_public_resolution(login):
    citizen, operator, inspector=login('citizen'),login('operator'),login('inspector')
    receipt=report(citizen);ident=receipt['case_id']
    act(operator,ident,'transition',status='investigating',reason='Acknowledged; check meter and schedule context')
    act(operator,ident,'assign',inspector_id='demo-inspector',reason='Inspect the water connection safely')
    detail=act(inspector,ident,'inspection',notes='Synthetic site inspection: leaking joint observed.',checklist={'site_verified':True},observations={'measured_volume_l':5,'measurement_minutes':2,'measurement_method':'Synthetic bucket test; not field validated','supply_context':'Illustrative stable supply period'})
    evidence=next(e['id'] for e in detail['evidence_records'] if e['kind']=='inspection')
    act(inspector,ident,'finding',finding='confirmed_leak',evidence_id=evidence,reason='Manual simulated site observation linked to this inspection')
    act(inspector,ident,'intervention',notes='Synthetic crew A replaced joint; repair reference TEST-1.',checklist={'site_verified':True})
    act(inspector,ident,'transition',status='monitoring',reason='Compare matched supply and demand periods')
    act(inspector,ident,'inspection',kind='follow_up',notes='Synthetic post-repair observation; no active leak at test point.',checklist={'site_verified':True},observations={'measured_volume_l':0,'measurement_minutes':2,'measurement_method':'Synthetic follow-up collection test'})
    case=operator.get('/api/v1/cases/'+ident).json()
    assert operator.post('/api/v1/cases/'+ident+'/transition',json={'version':case['version'],'status':'resolved','reason':'Internal decision alone is insufficient'}).status_code==422
    act(operator,ident,'transition',status='resolved',reason='Reviewed documented intervention and follow-up',public_summary='The joint repair and follow-up are recorded. Please challenge if the problem remains.')
    tracking=citizen.get('/api/v1/reports/'+receipt['id']).json()
    assert tracking['status']=='resolved'
    assert 'Synthetic crew A' not in str(tracking)
    act(operator,ident,'transition',status='closed',reason='Human reviewer accepts the documented outcome',public_summary='The reviewed investigation is closed. You may reopen it by challenging the outcome.')


def test_message_only_update_preserves_explicit_target_without_exposing_legacy_deadline(login):
    citizen, operator = login('citizen'), login('operator')
    receipt = report(citizen)
    ident = receipt['case_id']
    legacy_due = (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()
    with SessionLocal() as db:
        case = db.get(Case, ident)
        case.deadline_at = legacy_due
        case.evidence = {**case.evidence, 'service_target': None}
        db.commit()

    message = 'The observation is being reviewed by the water team.'
    result = act(operator, ident, 'public-update', reason=message)
    assert result['next_update_at'] is None
    assert citizen.get('/api/v1/reports/' + receipt['id']).json()['accountability']['next_update_at'] is None

    explicit_due = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    act(operator, ident, 'public-update', reason=message, next_update_at=explicit_due)
    for extra in ({}, {'next_update_at': None}):
        result = act(operator, ident, 'public-update', reason='A field visit is being coordinated; the recorded update target remains.', **extra)
        assert result['next_update_at'] == explicit_due
        assert citizen.get('/api/v1/reports/' + receipt['id']).json()['accountability']['next_update_at'] == explicit_due
        row = next(item for item in operator.get('/api/v1/operations/queue').json() if item['id'] == ident)
        assert row['next_update_at'] == explicit_due
    with SessionLocal() as db:
        assert db.get(Case, ident).deadline_at == explicit_due


def test_configured_targets_queue_public_update_and_deduplicated_escalation(login):
    admin, citizen, operator=login('admin'),login('citizen'),login('operator')
    policy=admin.get('/api/v1/operations/policy').json()
    body={'version':policy['version'],'reason':'Synthetic administrative pilot target only','rules':[{'domain':'water','severity':'medium','hours':12,'team':'Water pilot team','supervisor_id':'demo-admin','basis':'Synthetic pilot target; not a municipal commitment'}]}
    assert citizen.post('/api/v1/operations/policy',json=body).status_code==403
    saved=admin.post('/api/v1/operations/policy',json=body)
    assert saved.status_code==200,saved.text
    assert admin.post('/api/v1/operations/policy',json=body).status_code==409
    try:
        receipt=report(citizen);ident=receipt['case_id']
        assert receipt['accountability']['team']=='Water pilot team'
        assert receipt['accountability']['assignment']=='unassigned'
        assert any(r['id']==ident for r in operator.get('/api/v1/operations/queue').json())
        due=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()
        act(operator,ident,'public-update',reason='An inspector will review this observation; timing is a pilot target.',next_update_at=due)
        assert citizen.get('/api/v1/reports/'+receipt['id']).json()['accountability']['next_update_at']==due
        with SessionLocal() as db:
            c=db.get(Case,ident);c.deadline_at=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat();c.evidence={**c.evidence,'public_update':{}};db.commit()
            notify_overdue(db);db.commit();notify_overdue(db);db.commit()
            assert db.query(Notification).filter(Notification.case_id==ident,Notification.dedupe_key.like('%supervisor:%')).count()==1
            assert db.get(Case,ident).status=='needs_review'
        assert next(r for r in operator.get('/api/v1/operations/queue').json() if r['id']==ident)['overdue'] is True
    finally:
        current=admin.get('/api/v1/operations/policy').json()
        admin.post('/api/v1/operations/policy',json={'version':current['version'],'reason':'Restore pre-test policy configuration','rules':policy['rules']})
