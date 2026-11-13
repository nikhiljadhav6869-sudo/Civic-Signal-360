import {useEffect,useState} from 'react';
import {Download,Smartphone,QrCode,ArrowRight} from 'lucide-react';

type InstallPrompt=Event & {prompt:()=>Promise<void>;userChoice:Promise<{outcome:'accepted'|'dismissed'}>};
type InstallInfo={url:string|null;shareable:boolean};

export function InstallPage(){
  const [mr,setMr]=useState(false),[prompt,setPrompt]=useState<InstallPrompt|null>(null);
  const [standalone,setStandalone]=useState(()=>matchMedia('(display-mode: standalone)').matches||(navigator as Navigator & {standalone?:boolean}).standalone===true);
  const [info,setInfo]=useState<InstallInfo|null>(null),[notice,setNotice]=useState(''),[failed,setFailed]=useState(false),[qrFailed,setQrFailed]=useState(false);
  const [busy,setBusy]=useState(false);
  const t=(en:string,ma:string)=>mr?ma:en;
  useEffect(()=>{document.documentElement.lang=mr?'mr':'en';return()=>{document.documentElement.lang='en'}},[mr]);
  useEffect(()=>{
    const available=(event:Event)=>{event.preventDefault();setPrompt(event as InstallPrompt)};
    const installed=()=>{setStandalone(true);setPrompt(null)};
    window.addEventListener('beforeinstallprompt',available);window.addEventListener('appinstalled',installed);
    const controller=new AbortController();
    fetch('/api/v1/install',{signal:controller.signal}).then(r=>{if(!r.ok)throw Error();return r.json()}).then(setInfo).catch(()=>{if(!controller.signal.aborted)setFailed(true)});
    return()=>{controller.abort();window.removeEventListener('beforeinstallprompt',available);window.removeEventListener('appinstalled',installed)};
  },[]);
  async function install(){
    if(!prompt)return;setBusy(true);setNotice('');
    try{await prompt.prompt();const choice=await prompt.userChoice;setNotice(choice.outcome==='accepted'?t('Installation requested. Follow the browser confirmation.','स्थापनेची विनंती केली. ब्राउझरमधील पुष्टी पूर्ण करा.'):t('Installation cancelled. You can still use the website.','स्थापना रद्द केली. संकेतस्थळ वापरता येईल.'))}
    catch{setNotice(t('Use your browser menu to install this app.','अॅप स्थापित करण्यासाठी ब्राउझरचा मेनू वापरा.'))}
    finally{setPrompt(null);setBusy(false)}
  }
  async function copy(){try{await navigator.clipboard.writeText(info!.url!);setNotice(t('Installation link copied.','स्थापनेची लिंक कॉपी केली.'))}catch{setNotice(t('Copy the address shown below.','खालील पत्ता कॉपी करा.'))}}
  return <div className="install-page" lang={mr?'mr':'en'}>
    <header className="install-header"><a href="/" className="install-brand"><img src="/icons/icon-192.png" alt="" width="40" height="40"/>CivicSignal <strong>360</strong></a><button className="button secondary" onClick={()=>{setMr(!mr);setNotice('')}}>{mr?'English':'मराठी'}</button></header>
    <main className="install-main">
      <span className="eyebrow"><Smartphone size={16}/>{t('YOUR CITY, IN YOUR POCKET','आपले शहर, आपल्या हातात')}</span>
      <h1>{t('CivicSignal on your phone.','आपल्या फोनवर CivicSignal.')}</h1>
      <p className="install-lead">{t('Report water and civic problems, track updates and keep your city workspace close. Install the web app on iPhone or Android for free.','पाणी आणि नागरी समस्या नोंदवा, माहितीचा मागोवा घ्या आणि आपले कार्यक्षेत्र जवळ ठेवा. iPhone किंवा Android वर वेब अॅप मोफत स्थापित करा.')}</p>
      <div className="install-actions"><a href="/" className="button primary">{t('Open CivicSignal','CivicSignal उघडा')}<ArrowRight size={16}/></a>{prompt&&!standalone&&<button className="button primary" disabled={busy} onClick={()=>void install()}><Download size={16}/>{t('Install app','अॅप स्थापित करा')}</button>}</div>
      {standalone&&<p role="status">{t('You are using CivicSignal as an installed app.','आपण CivicSignal स्थापित अॅप म्हणून वापरत आहात.')}</p>}
      {notice&&<p role="status">{notice}</p>}
      <div className="install-grid">
        <section className="install-card"><h2>iPhone / iPad</h2><ol><li>{t('Open this page in Safari.','हे पृष्ठ Safari मध्ये उघडा.')}</li><li>{t('Tap Share, then Add to Home Screen.','Share दाबा, नंतर Add to Home Screen निवडा.')}</li><li>{t('Turn on Open as Web App if shown, then tap Add.','Open as Web App दिसल्यास सक्रिय करा, नंतर Add दाबा.')}</li></ol><p>{t('Scan with the Camera app to open this page.','हे पृष्ठ उघडण्यासाठी Camera अॅपने स्कॅन करा.')}</p></section>
        <section className="install-card"><h2>Android</h2><ol><li>{t('Open this page in Chrome.','हे पृष्ठ Chrome मध्ये उघडा.')}</li><li>{t('Tap Install app above when available, or open Chrome’s ⋮ menu.','वर Install app दिसल्यास दाबा किंवा Chrome चा ⋮ मेनू उघडा.')}</li><li>{t('Choose Install and create shortcut / Add to Home screen, then confirm Install.','Install and create shortcut / Add to Home screen निवडा, नंतर Install ची पुष्टी करा.')}</li></ol><p>{t('Menu names vary by browser version.','ब्राउझरच्या आवृत्तीनुसार मेनूची नावे बदलू शकतात.')}</p></section>
      </div>
      <section className="install-card install-share"><div><QrCode size={25}/><h2>{t('Scan to open and install','उघडण्यासाठी आणि स्थापित करण्यासाठी स्कॅन करा')}</h2><p>{t('One QR code for iPhone and Android. Scanning opens the installation page; installation still needs your confirmation.','iPhone आणि Android साठी एकच QR कोड. स्कॅन केल्यावर स्थापना पृष्ठ उघडेल; स्थापनेसाठी आपली पुष्टी आवश्यक आहे.')}</p>
      {info?.url&&<><a className="install-url" href={info.url}>{info.url}</a><div className="install-actions"><button className="button secondary" onClick={()=>void copy()}>{t('Copy install link','स्थापनेची लिंक कॉपी करा')}</button><a className="button secondary" href="/api/v1/install/qr.png" download="CivicSignal-360-install-QR.png">{t('Download QR code','QR कोड डाउनलोड करा')}</a></div></>}
      {failed?<p role="alert">{t('The installation address could not load. Refresh to retry.','स्थापनेचा पत्ता उपलब्ध नाही. पुन्हा प्रयत्न करण्यासाठी अद्ययावत करा.')}</p>:info&&!info.shareable?<p>{t('Public installation link pending deployment. A localhost address cannot install this app on another phone.','सार्वजनिक स्थापनेची लिंक प्रकाशनानंतर उपलब्ध होईल. localhost पत्त्यावरून दुसऱ्या फोनवर हे अॅप स्थापित करता येत नाही.')}</p>:!info?<p>{t('Loading installation link…','स्थापनेची लिंक मिळवत आहे…')}</p>:null}</div>
      {info?.shareable&&!qrFailed&&<img className="install-qr" src="/api/v1/install/qr.png" alt={t('QR code opening the CivicSignal installation page','CivicSignal स्थापना पृष्ठ उघडणारा QR कोड')} width="280" height="280" onError={()=>setQrFailed(true)}/>}{qrFailed&&<p role="alert">{t('QR image unavailable. Use the installation link.','QR प्रतिमा उपलब्ध नाही. स्थापनेची लिंक वापरा.')}</p>}
      </section>
      <p className="install-note">{t('This is an installable web app, not an App Store or Play Store download. Sign-in, report submission and current updates require internet. Previously enabled offline drafts remain on your device; installing does not make the service always online.','हे स्थापित करता येणारे वेब अॅप आहे; App Store किंवा Play Store वरील डाउनलोड नाही. प्रवेश, अहवाल पाठवणे आणि नवीन माहितीसाठी इंटरनेट आवश्यक आहे. पूर्वी सक्रिय केलेले ऑफलाइन मसुदे आपल्या उपकरणावर राहतात; स्थापना केल्याने सेवा कायम ऑनलाइन होत नाही.')}</p>
    </main><footer>{t('Independent software prototype • No hardware required','स्वतंत्र सॉफ्टवेअर प्रोटोटाइप • उपकरणांची आवश्यकता नाही')}</footer>
  </div>;
}
