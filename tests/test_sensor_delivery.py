import uuid
from datetime import datetime, timedelta, timezone

import pytest

from services.api.database import SessionLocal
from services.api.delivery import process_delivery
from services.api.domain import notify
from services.api.models import Asset, Audit, Configuration, Notification, Reading
from services.api.sensors import monitor_sensors


def device(login):
    admin=login('admin');ident='pilot-'+uuid.uuid4().hex[:16]
    with SessionLocal() as db:
        db.add(Asset(id=ident,name='Synthetic sensor pilot',domain='water',zone_id='river',kind='meter',provenance='Synthetic'));db.commit()
    body={'asset_id':ident,'source':'Simulated','stale_minutes':10,'offline_minutes':30}
    result=admin.post('/api/v1/sensors/register',json=body)
    assert result.status_code==200,result.text
    return admin,ident,{'Authorization':'Bearer '+result.json()['token']}


def reading(**values):
    return {'id':uuid.uuid4().hex,'timestamp':(datetime.now(timezone.utc)-timedelta(minutes=20)).isoformat(),'interval_minutes':5,'quantity':2,'unit':'m3','quality':'valid',**values}


def test_sensor_authenticated_units_duplicates_delayed_missing_and_scope(login):
    admin,ident,headers=device(login);url='/api/v1/sensors/'+ident+'/readings';row=reading()
    assert admin.post(url,json={'readings':[row]}).status_code==401
    first=admin.post(url,json={'readings':[row]},headers=headers);assert first.status_code==200,first.text
    assert first.json()['delayed']==1
    second=admin.post(url,json={'readings':[row]},headers=headers)
    assert second.json()['duplicates']==1 and second.json()['accepted']==0
    assert admin.post(url,json={'readings':[{**row,'quantity':9}]},headers=headers).status_code==409
    missing=reading(timestamp=(datetime.now(timezone.utc)-timedelta(minutes=10)).isoformat(),quantity=None,quality='missing',unit='L')
    assert admin.post(url,json={'readings':[missing]},headers=headers).status_code==200
    with SessionLocal() as db:
        assert db.get(Reading,row['id']).quantity==2000
        assert db.get(Reading,missing['id']).quantity is None
    assert login('citizen').get('/api/v1/sensors').status_code==403
    data=admin.get('/api/v1/sensors').json()
    assert 'token_hash' not in str(data) and headers['Authorization'] not in str(data)
    sensor=next(d for d in data if d['asset_id']==ident)
    assert sensor['state']=='reporting' and sensor['latest_quality']=='missing'
    bad=admin.post('/api/v1/sensors/register',json={'asset_id':ident,'source':'Live'})
    assert bad.status_code==422


@pytest.mark.parametrize('changes',[{'quantity':-1},{'quantity':None},{'unit':'gallons'},{'timestamp':'2026-01-01T00:00:00'},{'quality':'missing','quantity':2},{'timestamp':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}])
def test_invalid_sensor_readings_rejected_without_partial_packet(login,changes):
    admin,ident,headers=device(login);good=reading();bad=reading(**changes)
    response=admin.post('/api/v1/sensors/'+ident+'/readings',json={'readings':[good,bad]},headers=headers)
    assert response.status_code==422,response.text
    with SessionLocal() as db:assert db.get(Reading,good['id']) is None


def test_sensor_disconnect_recovery_no_alert_flood_and_key_rotation(login):
    admin,ident,headers=device(login);url='/api/v1/sensors/'+ident+'/readings'
    assert admin.post(url,json={'readings':[]},headers=headers).status_code==200
    with SessionLocal() as db:
        row=db.get(Configuration,'sensor:'+ident)
        row.value={**row.value,'last_contact':(datetime.now(timezone.utc)-timedelta(minutes=15)).isoformat()};db.commit()
        monitor_sensors(db);db.commit()
        assert db.get(Configuration,'sensor:'+ident).value['state']=='stale'
        row=db.get(Configuration,'sensor:'+ident);row.value={**row.value,'last_contact':(datetime.now(timezone.utc)-timedelta(minutes=45)).isoformat()};db.commit()
        monitor_sensors(db);db.commit()
        count=db.query(Notification).filter(Notification.dedupe_key.like('%sensor:'+ident+':%')).count()
        monitor_sensors(db);db.commit()
        assert db.query(Notification).filter(Notification.dedupe_key.like('%sensor:'+ident+':%')).count()==count
    assert admin.post(url,json={'readings':[reading()]},headers=headers).status_code==200
    sensor=next(d for d in admin.get('/api/v1/sensors').json() if d['asset_id']==ident)
    assert sensor['state']=='reporting' and sensor['recovered_at'] and sensor['observation_stale']
    rotated=admin.post('/api/v1/sensors/'+ident+'/rotate',json={}).json()
    assert admin.post(url,json={'readings':[]},headers=headers).status_code==401
    assert admin.post(url,json={'readings':[]},headers={'Authorization':'Bearer '+rotated['token']}).status_code==200


def test_notification_failure_retry_history_and_owner_access(login):
    citizen,operator=login('citizen'),login('operator')
    assert citizen.post('/api/v1/delivery/preference',json={'enabled':True}).status_code==200
    try:
        with SessionLocal() as db:
            event=uuid.uuid4().hex;notify(db,'demo-citizen',None,'Generic test notice',event);db.commit()
            item=db.query(Notification).filter_by(dedupe_key='demo-citizen:system:'+event).one()
            key='delivery:'+item.id;ident=item.id
            def failing(*args):raise RuntimeError('SECRET PROVIDER ERROR SHOULD NOT LEAK')
            for _ in range(3):
                row=db.get(Configuration,key);row.value={**row.value,'retry_at':'2000-01-01T00:00:00+00:00'};db.commit()
                process_delivery(db,transport=failing);db.expire_all()
            row=db.get(Configuration,key)
            assert row.value['state']=='failed' and len(row.value['attempts'])==3
        assert operator.post('/api/v1/delivery/'+ident+'/retry',json={}).status_code==404
        history=citizen.get('/api/v1/delivery').json()
        assert 'SECRET PROVIDER' not in str(history)
        assert citizen.post('/api/v1/delivery/'+ident+'/retry',json={}).status_code==200
        with SessionLocal() as db:
            process_delivery(db,transport=lambda *_:None);db.expire_all()
            record=db.get(Configuration,key).value
            assert record['state']=='provider_accepted' and len(record['attempts'])==4
    finally:
        citizen.post('/api/v1/delivery/preference',json={'enabled':False})
