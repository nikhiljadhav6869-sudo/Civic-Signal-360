import {useEffect, useState} from 'react';
import {api, ApiError, date, download, fmt, send, type CivicCase} from './api';
import {useInterfaceLanguage} from './uiLanguage';

export type WaterReviewSnapshot = {
  zone_id:string; snapshot_hash:string; configuration_version:number;
  review_inputs:Record<string,unknown>; window:{start:string;end_exclusive:string};
  balance:{unaccounted_l:number|null}; schedule_counts:Record<string,number>;
  source_observations:Array<unknown>;
};
type Attachment = {review:Record<string,unknown>;snapshot_hash:string;case_version:number;reason:string;idempotency_key:string};

export function AttachWaterReview({snapshot,onOpenCase}:{snapshot:WaterReviewSnapshot;onOpenCase:(item:CivicCase)=>void}) {
  const mr=useInterfaceLanguage()==='mr';
  const t=(en:string,marathi:string)=>mr?marathi:en;
  const [cases,setCases]=useState<CivicCase[]>([]);
  const [caseId,setCaseId]=useState('');
  const [reason,setReason]=useState('');
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const [revision,setRevision]=useState(0);
  const [loading,setLoading]=useState(true);
  const [pending,setPending]=useState<{caseId:string;body:Attachment}|null>(null);
  const [saved,setSaved]=useState<{evidence_id:string;case_id:string}|null>(null);
  useEffect(()=>{
    let active=true;setLoading(true);
    api('/cases').then((items:CivicCase[])=>{if(active){setCases(items.filter(c=>c.domain==='water'&&c.zone_id===snapshot.zone_id&&!['resolved','closed'].includes(c.status)));setCaseId('')}}).catch(e=>{if(active)setError(e.message)}).finally(()=>{if(active)setLoading(false)});
    return()=>{active=false};
  },[snapshot.zone_id,revision]);
  const attach=async()=>{
    const selected=cases.find(c=>c.id===caseId);
    if(!pending&&!selected)return;
    const attempt=pending||{caseId,body:{review:snapshot.review_inputs,snapshot_hash:snapshot.snapshot_hash,case_version:selected!.version,reason,idempotency_key:crypto.randomUUID()}};
    setPending(attempt);setBusy(true);setError('');
    try{
      const response=await send(`/water/zones/${snapshot.zone_id}/cases/${attempt.caseId}/reviews`,attempt.body);
      if(typeof response.evidence_id!=='string'||response.case_id!==attempt.caseId||response.snapshot_hash!==attempt.body.snapshot_hash)throw new Error('Unconfirmed attachment');
      setSaved(response);setPending(null);
    }
    catch(e){
      if(e instanceof ApiError&&e.status>=400&&e.status<500){setPending(null);setError(e.message)}
      else setError(t('Confirmation is unavailable. Retry this exact attachment before starting another. The retry cannot create a second record.','पुष्टी उपलब्ध नाही. दुसरी नोंद सुरू करण्यापूर्वी हीच जोडणी पुन्हा पाठवा. पुन्हा पाठवल्याने दुसरी प्रत तयार होणार नाही.'));
    }finally{setBusy(false)}
  };
  return <section className="water-review-attachment" aria-label={t('Attach water review','पाण्याचा आढावा जोडा')}>
    <h3>{t('Save to an Evidence Passport','पुरावा नोंदीत जतन करा')}</h3>
    <p className="helper">{t('Attach the reviewed readings, configuration and accounting assumptions to an open water case in this zone. This records context without changing the case decision.','तपासलेली मोजमापे, संरचना व हिशेबाची गृहितके या क्षेत्रातील उघड्या पाणी प्रकरणाला जोडा. प्रकरणाचा निर्णय बदलणार नाही.')}</p>
    {error&&<p role="alert">{error}</p>}
    {saved?<><p role="status">{t('Review attached. Evidence ID','आढावा जोडला. पुरावा क्रमांक')}: {saved.evidence_id}</p><button className="button secondary" disabled={busy} onClick={async()=>{setBusy(true);try{onOpenCase(await api('/cases/'+saved.case_id))}catch(e){setError(e instanceof Error?e.message:'Unable to open case')}finally{setBusy(false)}}}>{t('Open saved Evidence Passport','जतन केलेली पुरावा नोंद उघडा')}</button></>:<>
      <fieldset disabled={busy||!!pending||loading}>
        <label>{t('Water case for this review','या आढाव्यासाठी पाण्याचे प्रकरण')}<select value={caseId} onChange={e=>setCaseId(e.target.value)}><option value="">{t('Choose an open case','उघडे प्रकरण निवडा')}</option>{cases.map(c=><option key={c.id} value={c.id}>{c.title} · {c.id}</option>)}</select></label>
        <label>{t('Why this review is relevant','हा आढावा का संबंधित आहे')}<textarea value={reason} maxLength={2000} onChange={e=>setReason(e.target.value)}/></label>
      </fieldset>
      {!loading&&!cases.length&&<p role="status">{t('No authorized open water cases in this zone. Create or reopen a case through the normal review workflow.','या क्षेत्रात अधिकृत उघडी पाणी प्रकरणे नाहीत. नेहमीच्या पुनरावलोकन प्रक्रियेतून प्रकरण तयार करा किंवा पुन्हा उघडा.')}</p>}
      <div className="form-actions"><button className="button primary" disabled={busy||(!pending&&(!caseId||reason.trim().length<5))} onClick={attach}>{pending?t('Retry exact attachment','हीच जोडणी पुन्हा पाठवा'):t('Attach reviewed snapshot','तपासलेला आढावा जोडा')}</button><button className="button secondary" disabled={busy||!!pending} onClick={()=>{setError('');setRevision(v=>v+1)}}>{t('Refresh case list','प्रकरणांची यादी पुन्हा मिळवा')}</button></div>
      {pending&&<p role="status">{t('The exact pending request is held in this page. Keep it open until confirmation.','पुष्टी न झालेली मूळ विनंती या पृष्ठावर ठेवली आहे. पुष्टी मिळेपर्यंत पृष्ठ उघडे ठेवा.')}</p>}
    </>}
  </section>;
}

export function WaterReviewEvidence({record}:{record:{id:string;notes:string;created_at:string;observations:{water_review:WaterReviewSnapshot}}}) {
  const mr=useInterfaceLanguage()==='mr';
  const snapshot=record.observations.water_review;
  return <div className="saved-water-review" data-testid="saved-water-review">
    <strong>{mr?'जतन केलेला पाणीपुरवठा आढावा':'Saved water operations review'}</strong>
    <p>{record.notes}</p><small>{date(record.created_at)} · {record.id}</small>
    <p>{mr?'निवडलेला कालावधी (UTC)':'Selected window (UTC)'}: {snapshot.window.start} → {snapshot.window.end_exclusive}</p>
    <p>{mr?'संरचनेची आवृत्ती':'Configuration version'}: {snapshot.configuration_version} · {mr?'मूळ मोजमापे':'Source observations'}: {snapshot.source_observations.length}</p>
    <p>{mr?'हिशेबातील फरक':'Accounting residual'}: {snapshot.balance.unaccounted_l===null?(mr?'उपलब्ध नाही':'Unavailable'):fmt(snapshot.balance.unaccounted_l,2)+' L'}</p>
    <p className="helper">{mr?'नोंदवलेला संदर्भ; सिद्ध गळती किंवा प्रत्यक्ष स्थळ तपासणी नाही. सध्याची संरचना ऐतिहासिक वेळापत्रक सिद्ध करत नाही.':'Recorded context, not a confirmed leak or field inspection. Current configuration does not prove the historical supply schedule.'}</p>
    <details><summary>{mr?'आढाव्याची ओळख':'Snapshot identity'}</summary><code>{snapshot.snapshot_hash}</code></details>
    <button className="button secondary" onClick={()=>download(snapshot,'water-review-evidence-'+record.id+'.json')}>{mr?'जतन केलेला आढावा निर्यात करा':'Export saved water review'}</button>
  </div>;
}
