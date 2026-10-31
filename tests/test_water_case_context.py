from services.api.database import SessionLocal
from services.api.models import User


def test_live_quality_context_is_staff_scoped_and_never_in_citizen_tracking(login):
    operator, citizen, inspector=login('operator'),login('citizen'),login('inspector')
    case=next(c for c in operator.get('/api/v1/cases').json() if c['domain']=='water' and c['asset_id'])
    path='/api/v1/cases/'+case['id']+'/water-context'
    assert citizen.get(path).status_code==403
    assert inspector.get(path).status_code==403
    response=operator.get(path)
    assert response.status_code==200,response.text
    quality=response.json()
    assert quality['sample_count']==quality['valid_count']+quality['missing_count']+quality['invalid_count']
    assert quality['sample_count']>0 and quality['latest_interval_end']
    with SessionLocal() as db:
        user=db.get(User,'demo-operator');old=list(user.zones);user.zones=[];db.commit()
    try:assert operator.get(path).status_code==403
    finally:
        with SessionLocal() as db:db.get(User,'demo-operator').zones=old;db.commit()
    import uuid
    receipt=citizen.post('/api/v1/reports',json={'domain':'water','zone_id':case['zone_id'],'affected_asset_id':case['asset_id'],'title':'Private tracking test','description':'Synthetic citizen report linked to an asset','location':'Synthetic test location','idempotency_key':uuid.uuid4().hex})
    assert receipt.status_code==201,receipt.text
    receipt=receipt.json()
    assert citizen.get('/api/v1/cases/'+receipt['case_id']+'/water-context').status_code==403
    tracking=citizen.get('/api/v1/reports/'+receipt['id']).json()
    assert 'current_water_context' not in tracking and 'sources' not in tracking
