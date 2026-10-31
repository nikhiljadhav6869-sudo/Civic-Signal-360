"""Reproducible isolated sensor demo. No physical hardware or operational DB is used."""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
runtime = ROOT / '.runtime'
runtime.mkdir(exist_ok=True)
directory = Path(tempfile.mkdtemp(prefix='sensor-simulation-', dir=runtime))
os.environ['CIVIC_DATA_DIR'] = str(directory)
os.environ['DATABASE_URL'] = 'sqlite:///' + (directory / 'simulation.db').as_posix()
os.environ['CIVIC_DEMO_MODE'] = 'true'

from fastapi.testclient import TestClient
from services.api.main import app
from services.api.database import SessionLocal
from services.api.models import Asset
from services.api.sensors import monitor_sensors


class Clock(datetime):
    instant = datetime(2026, 10, 29, 10, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.instant if tz else cls.instant.replace(tzinfo=None)


results = {'provenance': 'Simulated in isolated temporary database', 'hardware_validated': False, 'phases': []}
with TestClient(app) as client, patch('services.api.sensors.datetime', Clock):
    auth = client.post('/api/v1/auth/login', json={'email':'admin@civicsignal.local','password':'CivicDemo!2026'}).json()
    client.headers['X-CSRF-Token'] = auth['csrf_token']
    with SessionLocal() as db:
        db.add(Asset(id='simulation-meter',name='Isolated simulator',domain='water',zone_id='river',kind='meter',provenance='Synthetic'));db.commit()
    registered=client.post('/api/v1/sensors/register',json={'asset_id':'simulation-meter','source':'Simulated','stale_minutes':10,'offline_minutes':30})
    assert registered.status_code==200,registered.text
    headers={'Authorization':'Bearer '+registered.json()['token']}

    def observe(label, minute, quantity, quality='valid'):
        row={'id':'simulation-'+label,'timestamp':(Clock.instant+timedelta(minutes=minute)).isoformat(),'interval_minutes':5,'quantity':quantity,'quality':quality,'unit':'L'}
        response=client.post('/api/v1/sensors/simulation-meter/readings',json={'readings':[row]},headers=headers)
        assert response.status_code==200,response.text
        snapshot(label)
        return row

    def snapshot(label):
        sensor=next(s for s in client.get('/api/v1/sensors').json() if s['asset_id']=='simulation-meter')
        results['phases'].append({'phase':label,'clock':Clock.instant.isoformat(),'state':sensor['state'],'quality':sensor['latest_quality'],'observation_stale':sensor['observation_stale'],'recovered_at':sensor['recovered_at']})

    normal=observe('normal',-15,5)
    observe('unusual_consumption_input_not_confirmed_leak',-10,50)
    observe('missing',-5,None,'missing')
    duplicate=client.post('/api/v1/sensors/simulation-meter/readings',json={'readings':[normal]},headers=headers).json()
    assert duplicate['duplicates']==1
    for minute,label in [(12,'stale'),(35,'offline')]:
        Clock.instant=datetime(2026,10,29,10,tzinfo=timezone.utc)+timedelta(minutes=minute)
        with SessionLocal() as db:monitor_sensors(db);db.commit()
        snapshot(label)
    Clock.instant+=timedelta(minutes=1)
    observe('recovery',-5,5)
assert [p['state'] for p in results['phases']]==['reporting','reporting','reporting','stale','offline','reporting']
output=ROOT/'artifacts'/'verification'/'sensor-simulation.json'
output.parent.mkdir(parents=True,exist_ok=True)
output.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=False,indent=2))
