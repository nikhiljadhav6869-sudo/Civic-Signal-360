import {useState} from 'react';
import {ApiError,send} from './api';
import {citizenDate} from './citizenFormat';
import {citizenDomains} from './citizenLanguage';

export type Accountability = {team:string;assignment:string;next_action:string;next_update_at:string|null;overdue:boolean;target_basis:string|null;public_update:string|null;public_update_at:string|null;resolution:{message:string;at:string}|null;version:number};
const nextSteps:Record<string,[string,string]> = {
  acknowledge:['Team to acknowledge and review','विभागाने दखल घेऊन आढावा घ्यावा'],assign:['Assign a field worker','क्षेत्रीय कर्मचारी नेमावा'],inspect:['Inspect the reported condition','नोंदवलेल्या स्थितीची तपासणी करावी'],monitor:['Record intervention follow-up','कार्यवाहीनंतर पाठपुरावा नोंदवावा'],follow_up:['Review follow-up evidence','पाठपुराव्याच्या पुराव्यांचा आढावा घ्यावा'],review_outcome:['Review the outcome; challenge if incorrect','निराकरण तपासा; चुकीचे असल्यास आक्षेप नोंदवा'],challenge_if_needed:['Challenge closure if the issue remains','समस्या कायम असल्यास आक्षेप नोंदवा'],review:['Review the case','प्रकरणाचा आढावा घ्यावा']
};
export function nextAction(key:string,mr:boolean){return (nextSteps[key]||nextSteps.review)[mr?1:0]}
export function ComplaintAccountability({reportId,status,value,mr,onChanged}:{reportId:string;status:string;value:Accountability;mr:boolean;onChanged:()=>Promise<void>}){
  const t=(en:string,marathi:string)=>mr?marathi:en;
  const [reason,setReason]=useState('');const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [notice,setNotice]=useState('');
  const [pending,setPending]=useState<{reason:string;version:number;idempotency_key:string}|null>(null);
  async function dispute(){
    const body=pending||{reason,version:value.version,idempotency_key:crypto.randomUUID()};
    setPending(body);setBusy(true);setError('');
    try{await send('/reports/'+reportId+'/dispute',body);setPending(null);setReason('');setNotice(t('Your challenge was accepted. The case is reopened for investigation.','आपला आक्षेप स्वीकारला. प्रकरण तपासासाठी पुन्हा उघडले आहे.'));try{await onChanged()}catch{setError(t('Challenge accepted; refresh tracking to see the latest status.','आक्षेप स्वीकारला; नवीन स्थिती पाहण्यासाठी पाठपुरावा अद्ययावत करा.'))}}
    catch(e){setError(e instanceof ApiError&&e.status===409?t('The case changed. Refresh tracking to check whether it is already reopened; your explanation is retained.','प्रकरण बदलले आहे. ते पुन्हा उघडले आहे का हे तपासण्यासाठी पाठपुरावा अद्ययावत करा; आपले स्पष्टीकरण ठेवले आहे.'):t('Not confirmed. Keep this page open and retry the same challenge when connected.','पुष्टी मिळाली नाही. हे पृष्ठ उघडे ठेवा आणि जोडणी झाल्यावर हाच आक्षेप पुन्हा पाठवा.'))}
    finally{setBusy(false)}
  }
  return <section className="accountability-card" aria-label={t('Complaint ownership and next action','तक्रारीची जबाबदारी आणि पुढील कार्यवाही')}>
    <h3>{t('Who is handling this?','जबाबदारी कोणाची आहे?')}</h3>
    <p>{t('Responsible team','जबाबदार विभाग')}: <strong>{mr?(citizenDomains[value.team]||value.team):value.team}</strong> · {value.assignment==='assigned'?t('Field worker assigned','क्षेत्रीय कर्मचारी नेमला आहे'):t('Unassigned queue — staff assignment pending','नेमणूक प्रलंबित यादी — कर्मचारी नेमणे बाकी')}</p>
    <p>{t('Next action','पुढील कार्यवाही')}: {nextAction(value.next_action,mr)}</p>
    <p>{t('Next update target','पुढील माहिती देण्याचे लक्ष्य')}: {value.next_update_at?citizenDate(value.next_update_at,mr?'mr':'en'):t('Not configured; no response time promised','निश्चित केलेले नाही; प्रतिसादाच्या वेळेचे आश्वासन दिलेले नाही')}{value.overdue&&<strong> · {t('Overdue — supervisor review needed','विलंब झाला — पर्यवेक्षकाचा आढावा आवश्यक')}</strong>}</p>
    {value.target_basis&&<p>{t('Target basis','लक्ष्याचा आधार')}: {value.target_basis}</p>}
    {value.public_update&&<p>{t('Latest public update','नागरिकांसाठी नवीन माहिती')}: {value.public_update}</p>}
    {value.resolution&&<p><strong>{t('Outcome explanation','निराकरणाचे स्पष्टीकरण')}: </strong>{value.resolution.message}</p>}
    {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
    {(['closed','resolved'].includes(status)||pending)&&<><label>{t('Explain why the outcome is incorrect (at least 10 characters)','निराकरण चुकीचे का आहे ते सांगा (किमान १० अक्षरे)')}<textarea value={reason} disabled={busy||!!pending} maxLength={2000} onChange={e=>setReason(e.target.value)}/></label><button className="button primary" disabled={busy||(!pending&&reason.trim().length<10)} onClick={()=>void dispute()}>{busy?t('Sending…','पाठवत आहे…'):pending?t('Retry the same challenge','हाच आक्षेप पुन्हा पाठवा'):t('Challenge outcome and reopen','आक्षेप नोंदवा आणि प्रकरण पुन्हा उघडा')}</button>{pending&&<button className="button secondary" disabled={busy} onClick={()=>void onChanged()}>{t('Refresh tracking','पाठपुरावा अद्ययावत करा')}</button>}</>}
  </section>;
}
