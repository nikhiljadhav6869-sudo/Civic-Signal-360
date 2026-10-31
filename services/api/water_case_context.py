"""Staff-only current water quality. Citizen report serialization never calls this endpoint."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from .database import get_db
from .domain import case_access
from .models import Asset, Configuration, Reading
from .security import current_user, in_scope

router = APIRouter(prefix="/api/v1")


@router.get('/cases/{case_id}/water-context')
def current_water_context(case_id: str, user=Depends(current_user), db=Depends(get_db)):
    if user.role not in {'admin','operator','inspector'}:
        raise HTTPException(403,'Authorized staff only; water telemetry is not public tracking data.')
    case = case_access(db,user,case_id)
    if case.domain != 'water':
        raise HTTPException(422,'Water case required.')
    result = {"scope": "Current registered-asset observations; not reconstructed detection inputs", "sample_count": 0, "valid_count": 0, "missing_count": 0, "invalid_count": 0, "latest_interval_end": None, "age_minutes": None, "gap_minutes": None, "sources": [], "sample_truncated": False, "stale": None}
    asset=db.get(Asset,case.asset_id) if case.asset_id else None
    if not asset or case.provenance=='Simulated':
        return result
    if asset.domain!='water' or asset.zone_id!=case.zone_id or not in_scope(user,asset.domain,asset.zone_id):
        raise HTTPException(403,'Asset is outside this authorized water investigation.')
    rows=db.query(Reading).filter_by(asset_id=asset.id,domain='water').order_by(Reading.timestamp.desc()).limit(2001).all()
    result['sample_truncated']=len(rows)>2000
    rows=rows[:2000]; intervals=[]
    for row in rows:
        start=datetime.fromisoformat(row.timestamp.replace('Z','+00:00'))
        intervals.append((start,start+timedelta(minutes=row.interval_minutes)))
        key='valid_count' if row.quality_flag=='valid' and row.quantity is not None else 'missing_count' if row.quantity is None or row.quality_flag=='missing' else 'invalid_count'
        result[key]+=1
    result['sample_count']=len(rows);result['sources']=sorted({r.source for r in rows})
    if intervals:
        intervals.sort();covered=intervals[0][1];gaps=0
        for start,end in intervals[1:]:
            gaps+=max(0,(start-covered).total_seconds()/60);covered=max(covered,end)
        result['gap_minutes']=round(gaps,2)
        result['latest_interval_end']=covered.isoformat()
        result['age_minutes']=round((datetime.now(timezone.utc)-covered).total_seconds()/60,2)
        device=db.get(Configuration,'sensor:'+asset.id)
        if device:result['stale']=result['age_minutes']>device.value['stale_minutes']
    return result
