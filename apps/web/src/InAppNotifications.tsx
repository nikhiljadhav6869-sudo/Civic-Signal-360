import {useState} from 'react';
import {api,type Bootstrap,type CivicCase,send} from './api';
import {citizenDate} from './citizenFormat';
import {citizenStatus} from './citizenLanguage';
import {useInterfaceLanguage} from './uiLanguage';

function translatedTitle(title:string,mr:boolean){
  if(!mr)return title;
  if(title.startsWith('Report received: '))return 'अहवाल प्राप्त: '+title.slice(17);
  if(title.startsWith('Review overdue: '))return 'आढाव्यास विलंब: '+title.slice(16);
  if(title==='Supervisor review overdue')return 'पर्यवेक्षकाच्या आढाव्यास विलंब';
  if(title==='Citizen observation linked for review')return 'नागरिकांचे निरीक्षण आढाव्यासाठी जोडले';
  const sensor=/^Water sensor (.*): (reporting|stale|offline|disabled)$/.exec(title);
  if(sensor)return 'पाण्याचा सेन्सर '+sensor[1]+': '+({reporting:'संपर्क सुरू',stale:'संपर्क जुना',offline:'संपर्क बंद',disabled:'निष्क्रिय'}[sensor[2]]);
  const at=title.lastIndexOf(': ');const status=title.slice(at+2).replaceAll(' ','_');
  if(at>=0&&['needs_review','investigating','assigned','intervention','monitoring','resolved','closed'].includes(status))return title.slice(0,at)+': '+citizenStatus(status,true);
  return title; // Preserve citizen/analyst free text rather than fabricating a translation.
}

export function InAppNotifications({data,select,refresh,go}:{data:Bootstrap;select:(c:CivicCase)=>void;refresh:()=>Promise<void>;go:(p:string)=>void}){
  const mr=useInterfaceLanguage()==='mr';const t=(en:string,ma:string)=>mr?ma:en;const [error,setError]=useState('');const [busy,setBusy]=useState('');
  async function act(id:string,fn:()=>Promise<void>){setBusy(id);setError('');try{await fn()}catch{setError(t('Unable to update notifications. Refresh and retry.','सूचना अद्ययावत करता आल्या नाहीत. पुन्हा प्रयत्न करा.'))}finally{setBusy('')}}
  return <section className="panel"><h2>{t('Updates that keep the work moving','काम पुढे नेणाऱ्या सूचना')}</h2><p>{data.notifications.filter(n=>!n.read).length} {t('unread','न वाचलेल्या')}</p>{error&&<p role="alert">{error}</p>}<div className="notification-list">{data.notifications.map(n=><div key={n.id} className={n.read?'read':''}><div><strong>{translatedTitle(n.title,mr)}</strong><p>{t('An authorized update is available. Original descriptions stay as written.','अधिकृत अद्ययावत माहिती उपलब्ध आहे. मूळ वर्णने जशी लिहिली तशी ठेवली आहेत.')}</p><small>{citizenDate(n.created_at,mr?'mr':'en')}</small></div>{n.case_id&&<button className="text-button" disabled={!!busy} onClick={()=>void act(n.id,async()=>{if(data.user.role==='citizen')go('/reports');else select(await api('/cases/'+n.case_id))})}>{t('View case','प्रकरण पहा')}</button>}{!n.read&&<button className="button secondary" disabled={!!busy} onClick={()=>void act(n.id,async()=>{await send('/notifications/'+n.id+'/read',{});await refresh()})}>{t('Mark read','वाचले म्हणून नोंदवा')}</button>}</div>)}</div>{!data.notifications.length&&<p>{t('No new authorized updates.','नवीन अधिकृत सूचना नाहीत.')}</p>}</section>;
}
