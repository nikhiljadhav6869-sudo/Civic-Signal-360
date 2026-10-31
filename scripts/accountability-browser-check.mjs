import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const {chromium}=createRequire(import.meta.url)('playwright');
const base=process.env.CIVIC_BASE_URL;
if(!base||!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base))throw new Error('Use an isolated local synthetic server.');
const browser=await chromium.launch({headless:true,executablePath:process.env.CIVIC_BROWSER_PATH});
const results={checks:[],errors:[]};const actors=[];
async function actor(role,mr){
  const context=await browser.newContext({viewport:{width:1440,height:1000},timezoneId:'Asia/Kolkata',reducedMotion:'reduce'});
  await context.route('**/*',r=>new URL(r.request().url()).origin===base||/^(blob|data):/.test(r.request().url())?r.continue():r.abort());
  const auth=await (await context.request.post(base+'/api/v1/auth/login',{data:{email:role+'@civicsignal.local',password:'CivicDemo!2026'}})).json();
  await context.addInitScript(({role,mr})=>{localStorage.setItem('civic-interface-language-demo-'+role,mr?'mr':'en');sessionStorage.setItem('civic-language-demo-'+role,mr?'mr':'en')},{role,mr});
  const page=await context.newPage();page.on('pageerror',e=>results.errors.push(e.message));
  const request=async(path,body)=>{const r=await context.request.post(base+'/api/v1'+path,{data:body,headers:{'X-CSRF-Token':auth.csrf_token}});assert.ok(r.ok(),await r.text());return r.json()};
  const a={context,page,request,mr};actors.push(a);return a;
}
async function open(a,id){await a.page.goto(base+'/overview');await a.page.locator('.operations-workbench>label').last().locator('select').selectOption(id);const core=a.page.locator('.core-case');await core.locator('fieldset').waitFor();return core}
async function work(a,id,action,reason,fill){
  const core=await open(a,id);await core.getByLabel(a.mr?'कृती':'Action',{exact:true}).selectOption(action);
  await core.getByLabel(a.mr?'अंतर्गत निष्कर्ष / निर्णयाचे कारण (किमान १० अक्षरे)':'Internal findings / decision reason (at least 10 characters)',{exact:true}).fill(reason);
  if(fill)await fill(core);
  const response=a.page.waitForResponse(r=>r.request().method()==='POST'&&r.url().includes('/api/v1/cases/'+id+'/'));
  await core.getByRole('button',{name:a.mr?'कार्यवाही जतन करा':'Save action',exact:true}).click();const r=await response;assert.equal(r.status(),200,await r.text());
  await core.getByText(a.mr?'सर्व्हरवर जतन केले.':'Saved on the server.',{exact:true}).waitFor();return r.json();
}
async function check(name,fn){try{await fn();results.checks.push({name,status:'passed'});console.log('PASS',name)}catch(e){results.checks.push({name,status:'failed',error:e.message});console.error('FAIL',name,e.message);for(let i=0;i<actors.length;i++){await actors[i].page.screenshot({path:'artifacts/verification/accountability-failure-'+i+'.png',fullPage:true}).catch(()=>{});await fs.writeFile('artifacts/verification/accountability-failure-'+i+'.txt',await actors[i].page.locator('body').innerText()).catch(()=>{})}}}
try{
  for(const mr of [false,true])await check('Citizen submission, complete water workflow and lost-response dispute retry '+(mr?'Marathi':'English'),async()=>{
    const citizen=await actor('citizen',mr),operator=await actor('operator',mr),inspector=await actor('inspector',mr);
    const title='Synthetic browser water '+(mr?'MR':'EN')+' '+Date.now();const page=citizen.page;
    await page.goto(base+'/report');const form=page.locator('.report-form');
    await form.locator('.report-categories button').filter({hasText:mr?'पाणी':'Water'}).first().click();
    const next=()=>form.getByRole('button',{name:mr?'पुढे':'Continue',exact:true}).click();
    await next();await form.getByLabel(mr?'सेवा क्षेत्र':'Service zone',{exact:true}).selectOption('river');await form.getByLabel(mr?'ठिकाण किंवा जवळची खूण':'Location or nearby landmark').fill('Synthetic pilot point');await next();
    await form.getByLabel(mr?'आपण काय पाहिले?':'What did you notice?').fill(title);await form.getByLabel(mr?'निरीक्षणाचे वर्णन करा':'Describe your observation').fill('Synthetic water observation for browser verification.');await next();
    const submitted=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/api/v1/reports'));
    await form.getByRole('button',{name:mr?'अहवाल पाठवा':'Submit report',exact:true}).click();const receipt=await (await submitted).json();await form.locator('.receipt').waitFor();
    await work(operator,receipt.case_id,'investigating','Acknowledge and check supply and baseline context');
    await work(operator,receipt.case_id,'assign','Assign site verification to the scoped inspector',async core=>core.getByLabel(mr?'मुख्य तपासनीस':'Lead inspector',{exact:true}).selectOption('demo-inspector'));
    await work(inspector,receipt.case_id,'inspection','Synthetic site verification of a suspected leaking joint',async core=>core.getByRole('checkbox',{name:mr?'मी स्थळावर या स्थितीची प्रत्यक्ष पडताळणी केली':'I personally verified this condition on site'}).check());
    await work(inspector,receipt.case_id,'finding','Synthetic observed leak classification, not a field validation',async core=>{await core.getByLabel(mr?'तपासणीचा पुरावा':'Inspection evidence',{exact:true}).selectOption({index:1});await core.getByLabel(mr?'निष्कर्ष':'Finding',{exact:true}).selectOption('confirmed_leak')});
    await work(inspector,receipt.case_id,'intervention','Synthetic crew and replaced joint record TEST-REPAIR');
    await work(inspector,receipt.case_id,'monitoring','Begin observations after the synthetic intervention');
    await work(inspector,receipt.case_id,'follow_up','Synthetic follow-up after repair; verify equivalent supply conditions');
    await work(operator,receipt.case_id,'resolved','PRIVATE_INTERNAL_REVIEW_EXCLUDED_FROM_CITIZEN',async core=>core.getByLabel(mr?'नागरिकांसाठी निराकरणाचे स्पष्टीकरण — अंतर्गत किंवा वैयक्तिक माहिती नको':'Citizen-facing outcome explanation — no internal or personal information',{exact:true}).fill('Synthetic repair and follow-up reviewed. Please challenge if the issue remains.'));
    await page.goto(base+'/reports');await page.locator('.report-list>button').filter({hasText:title}).click();
    const tracking=page.locator('#report-tracking');await tracking.waitFor();assert.ok(!(await tracking.innerText()).includes('PRIVATE_INTERNAL_REVIEW'));
    await tracking.getByLabel(mr?'निराकरण चुकीचे का आहे ते सांगा (किमान १० अक्षरे)':'Explain why the outcome is incorrect (at least 10 characters)').fill('Water is still visible; please inspect again.');
    let lost=false;
    await page.route('**/api/v1/reports/*/dispute',async route=>{if(!lost){lost=true;const response=await route.fetch();assert.equal(response.status(),200);await route.abort('failed')}else await route.continue()});
    await tracking.getByRole('button',{name:mr?'आक्षेप नोंदवा आणि प्रकरण पुन्हा उघडा':'Challenge outcome and reopen',exact:true}).click();await tracking.getByRole('alert').waitFor();
    await tracking.getByRole('button',{name:mr?'हाच आक्षेप पुन्हा पाठवा':'Retry the same challenge',exact:true}).click();
    await tracking.getByText(mr?'आपला आक्षेप स्वीकारला. प्रकरण तपासासाठी पुन्हा उघडले आहे.':'Your challenge was accepted. The case is reopened for investigation.',{exact:true}).waitFor();
    const current=await (await citizen.context.request.get(base+'/api/v1/reports/'+receipt.id)).json();assert.equal(current.status,'investigating');assert.equal(current.timeline.filter(e=>e.action==='citizen_dispute').length,1);
    for(const width of [390,768,1440]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);await page.screenshot({path:`artifacts/verification/accountability-citizen-${mr?'mr':'en'}-${width}.png`,fullPage:true})}
    const core=await open(inspector,receipt.case_id);await core.getByLabel(mr?'कृती':'Action',{exact:true}).focus();await inspector.page.keyboard.press('Tab');assert.equal(await core.locator('textarea').first().evaluate(el=>el===document.activeElement),true);
    await inspector.page.setViewportSize({width:390,height:900});assert.equal(await inspector.page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'Staff view must fit mobile width');await inspector.page.screenshot({path:`artifacts/verification/accountability-staff-${mr?'mr':'en'}-390.png`,fullPage:true});
  });
}finally{await fs.mkdir('artifacts/verification',{recursive:true});await fs.writeFile('artifacts/verification/accountability-browser.json',JSON.stringify(results,null,2));await browser.close()}
if(results.errors.length||results.checks.some(c=>c.status!=='passed'))process.exitCode=1;
