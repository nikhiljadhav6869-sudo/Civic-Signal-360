import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const {chromium}=createRequire(import.meta.url)('playwright');
const base=process.env.CIVIC_BASE_URL;
if(!base||!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base))throw Error('Use an isolated synthetic local preview.');
const browser=await chromium.launch({headless:true,executablePath:process.env.CIVIC_BROWSER_PATH});
const results={provenance:'Local synthetic software-only acceptance; no hardware or live email',checks:[],errors:[]};
const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
await context.route('**/*',route=>new URL(route.request().url()).origin===base||/^(blob|data):/.test(route.request().url())?route.continue():route.abort());
let auth;
for(let attempt=0;attempt<3;attempt++){
  auth=await context.request.post(base+'/api/v1/auth/login',{data:{email:'admin@civicsignal.local',password:'CivicDemo!2026'}});
  if(auth.status()!==429)break;
  const retryAfter=Number(auth.headers()['retry-after']);
  if(attempt===2)break;
  await new Promise(resolve=>setTimeout(resolve,(Number.isFinite(retryAfter)?Math.max(1,Math.min(65,retryAfter)):60)*1000+1000));
}
assert.equal(auth.status(),200,'Demo administrator sign-in failed: '+auth.status()+' '+await auth.text());
const {csrf_token}=await auth.json();
const page=await context.newPage();page.on('pageerror',e=>results.errors.push(e.message));
const csp=[];page.on('console',message=>{if(message.type()==='error'&&/content security policy|violates.*directive/i.test(message.text()))csp.push(message.text())});
async function check(name,fn){try{await fn();results.checks.push({name,status:'passed'});console.log('PASS',name)}catch(e){results.checks.push({name,status:'failed',error:e.message});console.error('FAIL',name,e.message);await page.screenshot({path:'artifacts/verification/software-failure.png',fullPage:true}).catch(()=>{})}}
const oldPolicy=await (await context.request.get(base+'/api/v1/operations/retention')).json();
try{
  await check('Software-only data guide and keyboard skip link',async()=>{
    await page.goto(base+'/lab');await page.getByRole('heading',{name:'Software-only water intelligence'}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Register device',exact:true}).count(),0);
    await page.locator('.skip-link').focus();await page.keyboard.press('Enter');assert.equal(await page.locator('#main').evaluate(el=>el===document.activeElement),true);
    await page.getByRole('button',{name:'Import readings',exact:true}).click();await page.getByRole('link',{name:'Download CSV template',exact:true}).waitFor();
  });
  await check('Admin can save and preview temporary retention; unsaved policy blocks preview',async()=>{
    await page.goto(base+'/admin');const panel=page.locator('.operational-controls');await panel.getByRole('heading',{name:'Service activity'}).waitFor();
    await panel.getByLabel('Enable approved temporary-data cleanup',{exact:true}).check();
    await panel.getByLabel(/^Approved retention basis/).fill('Synthetic browser policy; never a municipal commitment');
    await panel.getByLabel('Reason for this operation',{exact:true}).fill('Review synthetic temporary records while preserving case evidence');
    assert.equal(await panel.getByRole('button',{name:'Preview eligible records',exact:true}).isDisabled(),true);
    await panel.getByRole('button',{name:'Save retention policy',exact:true}).click();await panel.getByText('Policy saved. Nothing has been deleted.',{exact:true}).waitFor();
    await panel.getByRole('button',{name:'Preview eligible records',exact:true}).click();await panel.getByText(/Eligible expired sessions/).waitFor();
    assert.equal(await panel.getByRole('button',{name:'Delete previewed temporary records',exact:true}).isDisabled(),true);
    await panel.getByLabel('Days to retain an uncommitted CSV preview',{exact:true}).fill('31');
    assert.equal(await panel.getByRole('button',{name:'Preview eligible records',exact:true}).isDisabled(),true);
    assert.equal(await panel.getByRole('button',{name:'Delete previewed temporary records',exact:true}).count(),0);
  });
  await check('Advanced Marathi controls, document language and responsive admin forms',async()=>{
    await page.getByRole('button',{name:'Switch interface language to Marathi',exact:true}).click();
    await page.getByRole('heading',{name:'सॉफ्टवेअर कामकाज आणि डेटा जतन',exact:true}).waitFor();
    assert.equal(await page.locator('html').getAttribute('lang'),'mr');
    await page.locator('.page-tabs').getByRole('button',{name:'सेटिंग',exact:true}).click();
    await page.locator('.admin-editor summary').click();await page.getByLabel('पाणी दर · रुपये प्रति m³',{exact:true}).waitFor();
    for(const width of [390,768,1440]){await page.setViewportSize({width,height:1000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);await page.screenshot({path:`artifacts/verification/software-admin-mr-${width}.png`,fullPage:true})}
    await page.goto(base+'/lab');await page.getByRole('heading',{name:'फक्त सॉफ्टवेअरवर आधारित पाणी विश्लेषण'}).waitFor();
    await page.getByRole('button',{name:'निरीक्षणे आयात करा',exact:true}).click();await page.getByRole('link',{name:'CSV नमुना डाउनलोड करा',exact:true}).waitFor();
    await page.goto(base+'/settings');await page.getByLabel(/^वेळक्षेत्र/).waitFor();
    assert.equal(await page.locator('html').getAttribute('lang'),'mr');
  });
  await check('Selected admin, data, forecast and preferences controls have accessible names',async()=>{
    for(const path of ['/admin','/lab','/forecast','/settings']){
      await page.goto(base+path);await page.locator('.page-heading h1').waitFor();await page.locator('.loading').waitFor({state:'hidden'}).catch(()=>{});
      const unnamed=await page.locator('button,input,textarea,select').evaluateAll(elements=>elements.filter(el=>{
        if(!el.getClientRects().length||el.type==='hidden')return false;
        const labelledBy=(el.getAttribute('aria-labelledby')||'').split(/\s+/).map(id=>document.getElementById(id)?.textContent||'').join('');
        const labels=el.labels?[...el.labels].map(l=>l.textContent||'').join(''):'';
        return !(el.getAttribute('aria-label')||labelledBy||labels||(el.tagName==='BUTTON'?el.textContent:'')||el.getAttribute('title')||'').trim();
      }).map(el=>({tag:el.tagName,type:el.type,html:el.outerHTML.slice(0,200)})));
      assert.deepEqual(unnamed,[],path+' has unnamed controls');
    }
    assert.deepEqual(csp,[],'Content security policy blocked application resources');
  });
}finally{
  const current=await (await context.request.get(base+'/api/v1/operations/retention')).json();
  const restored=await context.request.post(base+'/api/v1/operations/retention',{data:{...oldPolicy,version:current.version,basis:oldPolicy.basis||'Restore disabled synthetic test policy; no retention approval',reason:'Restore policy after software browser acceptance checks'},headers:{'X-CSRF-Token':csrf_token}});
  assert.ok(restored.ok(),'Restore temporary policy after acceptance');
  await fs.mkdir('artifacts/verification',{recursive:true});await fs.writeFile('artifacts/verification/software-only-browser.json',JSON.stringify(results,null,2));await browser.close();
}
if(results.errors.length||results.checks.some(c=>c.status==='failed'))process.exitCode=1;
