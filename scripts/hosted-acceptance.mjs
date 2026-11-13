/** Read-only by default. Optional hosted checks use a dedicated citizen account. */
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const mode=process.argv[2]||'--read-only';
assert.ok(['--read-only','--authenticated','--write','--verify'].includes(mode),'Choose --read-only, --authenticated, --write or --verify.');
const origin=process.env.CIVIC_HOSTED_ORIGIN||'https://civicsignal-360.onrender.com';
const url=new URL(origin);
assert.equal(url.protocol,'https:','Hosted checks require HTTPS.');
assert.equal(url.pathname,'/','Use an origin, without a path.');
assert.ok(!url.username&&!url.password&&!url.search&&!url.hash,'Origin must not contain credentials or query data.');
assert.ok(url.hostname.includes('.')&&!/^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(url.hostname),'Use a public host.');
const output={mode,origin:url.origin,checks:[],status:'failed'};

async function request(path,{method='GET',body,cookie,csrf}={}){
  assert.ok(path.startsWith('/')&&!path.startsWith('//'),'Only same-origin paths are allowed.');
  const target=new URL(path,url.origin);
  assert.equal(target.origin,url.origin);
  const headers={Accept:'application/json'};
  if(cookie)headers.Cookie=cookie;
  if(csrf)headers['X-CSRF-Token']=csrf;
  if(body&&!(body instanceof FormData)){headers['Content-Type']='application/json';body=JSON.stringify(body)}
  return fetch(target,{method,headers,body,redirect:'error',signal:AbortSignal.timeout(90000)});
}
async function json(response,expected){
  assert.ok(expected.includes(response.status),`Expected HTTP ${expected.join('/')} but received ${response.status}.`);
  return response.json();
}
async function signIn(email,password){
  assert.ok(email&&password,'Set CIVIC_ACCEPTANCE_EMAIL and CIVIC_ACCEPTANCE_PASSWORD in this terminal only.');
  let response=await request('/api/v1/auth/login',{method:'POST',body:{email,password}});
  if(response.status===429){
    const seconds=Math.min(65,Math.max(1,Number(response.headers.get('retry-after'))||60));
    await new Promise(resolve=>setTimeout(resolve,(seconds+1)*1000));
    response=await request('/api/v1/auth/login',{method:'POST',body:{email,password}});
  }
  const data=await json(response,[200]);
  const setCookie=response.headers.getSetCookie().find(value=>value.startsWith('civic_session='));
  assert.ok(setCookie,'Sign-in did not set a session cookie.');
  const cookie=setCookie.split(';',1)[0];
  assert.ok(data.csrf_token&&data.user?.role,'Sign-in response is incomplete.');
  return {cookie,csrf:data.csrf_token,role:data.user.role};
}

try{
  const health=await json(await request('/api/v1/health'),[200]);
  assert.equal(health.status,'ok');assert.equal(health.demo_mode,false,'This check targets the non-demo deployment.');
  output.checks.push('Healthy non-demo API');
  const publicData=await json(await request('/api/v1/public'),[200]);
  assert.equal(publicData.demo_mode,false);
  output.service_zone_count=publicData.zones.length;
  output.checks.push('Public metadata');
  const install=await json(await request('/api/v1/install'),[200]);
  assert.equal(install.url,url.origin+'/install');
  assert.equal((await request('/api/v1/install/qr.png')).status,200);
  output.checks.push('Phone installation URL and QR');
  assert.equal((await request('/api/v1/auth/me')).status,401);
  assert.equal((await request('/api/v1/reports')).status,401);
  output.checks.push('Private API rejects unauthenticated access');

  if(mode!=='--read-only'){
    const session=await signIn(process.env.CIVIC_ACCEPTANCE_EMAIL,process.env.CIVIC_ACCEPTANCE_PASSWORD);
    const me=await json(await request('/api/v1/auth/me',{cookie:session.cookie}),[200]);
    assert.equal(me.user.role,session.role);
    const bootstrap=await json(await request('/api/v1/bootstrap',{cookie:session.cookie}),[200]);
    const reports=await json(await request('/api/v1/reports',{cookie:session.cookie}),[200]);
    assert.ok(Array.isArray(reports)&&Array.isArray(bootstrap.zones));
    output.account_role=session.role;
    output.checks.push('Authenticated session, bootstrap and authorized reports');

    if(mode==='--write'){
      assert.equal(process.env.CIVIC_ACCEPTANCE_ALLOW_WRITE,'yes','Set CIVIC_ACCEPTANCE_ALLOW_WRITE=yes to acknowledge permanent synthetic test records.');
      assert.equal(session.role,'citizen','Use a dedicated citizen test account, not the administrator account.');
      assert.ok(bootstrap.zones.length,'Create a test service zone in Administration before submitting a report.');
      const runId=process.env.CIVIC_ACCEPTANCE_RUN_ID;
      assert.ok(runId&&/^[A-Za-z0-9_-]{8,50}$/.test(runId),'Set a reusable CIVIC_ACCEPTANCE_RUN_ID of 8–50 letters/numbers/_/-.');
      const title='Synthetic hosted acceptance '+runId;
      const report=await json(await request('/api/v1/reports',{method:'POST',cookie:session.cookie,csrf:session.csrf,body:{domain:'water',zone_id:bootstrap.zones[0].id,title,description:'Synthetic software acceptance record. No real water fault is claimed.',location:'Synthetic test location, not a real address',idempotency_key:runId}}),[200,201]);
      assert.ok(report.id&&report.case_id);
      output.report_id=report.id;output.case_id=report.case_id;output.run_id=runId;
      output.checks.push('Idempotent synthetic citizen report');
      const photo=new FormData();
      photo.set('file',new Blob([await readFile(new URL('../apps/web/public/icons/icon-192.png',import.meta.url))],{type:'image/png'}),'synthetic-acceptance.png');
      photo.set('notes','Synthetic acceptance image; not a civic defect photograph.');
      photo.set('idempotency_key',runId+'-image');
      const evidence=await json(await request(`/api/v1/cases/${report.case_id}/evidence`,{method:'POST',cookie:session.cookie,csrf:session.csrf,body:photo}),[200]);
      assert.ok(evidence.id);
      output.evidence_id=evidence.id;
      output.checks.push('Idempotent synthetic image upload');
      const receipt=await json(await request(`/api/v1/reports/${report.id}`,{cookie:session.cookie}),[200]);
      assert.equal(receipt.case_id,report.case_id);
      const image=await request(`/api/v1/evidence/${evidence.id}/download`,{cookie:session.cookie});
      assert.equal(image.status,200);assert.match(image.headers.get('content-type')||'',/^image\/jpeg/);
      const bytes=new Uint8Array(await image.arrayBuffer());assert.ok(bytes.length>2&&bytes[0]===255&&bytes[1]===216);
      assert.equal((await request(`/api/v1/evidence/${evidence.id}/download`)).status,401);
      output.checks.push('Owner receipt and image readable; anonymous image download denied');
    }
    if(mode==='--verify'){
      const reportId=process.env.CIVIC_ACCEPTANCE_REPORT_ID;
      const evidenceId=process.env.CIVIC_ACCEPTANCE_EVIDENCE_ID;
      assert.ok(reportId&&evidenceId,'Set the report and evidence IDs from the earlier --write result.');
      const receipt=await json(await request(`/api/v1/reports/${encodeURIComponent(reportId)}`,{cookie:session.cookie}),[200]);
      assert.equal(receipt.id,reportId);
      const image=await request(`/api/v1/evidence/${encodeURIComponent(evidenceId)}/download`,{cookie:session.cookie});
      assert.equal(image.status,200);assert.match(image.headers.get('content-type')||'',/^image\/jpeg/);
      output.report_id=reportId;output.evidence_id=evidenceId;
      output.checks.push('Report and image persisted after a separate run');
    }
  }
  output.status='passed';
}catch(error){output.error=error.message;process.exitCode=1}
console.log(JSON.stringify(output,null,2));
