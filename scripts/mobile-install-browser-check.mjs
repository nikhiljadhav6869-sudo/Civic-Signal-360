import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const {chromium}=createRequire(import.meta.url)('playwright');
const base=process.env.CIVIC_BASE_URL;
if(!base||!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base))throw Error('Use an isolated local preview.');
const browser=await chromium.launch({headless:true,executablePath:process.env.CIVIC_BROWSER_PATH});
const context=await browser.newContext({viewport:{width:390,height:844}});
const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
const result={scope:'Local mobile web-app installation checks; physical device installation unverified',checks:[]};
try{
  await page.goto(base+'/install');await page.getByRole('heading',{name:'CivicSignal on your phone.'}).waitFor();
  const manifest=await (await context.request.get(base+'/manifest.webmanifest')).json();assert.equal(manifest.display,'standalone');
  for(const icon of manifest.icons)assert.equal((await context.request.get(base+icon.src)).status(),200);
  await page.waitForFunction(()=>document.querySelector('.install-qr')?.naturalWidth>0);
  const metadata=await (await context.request.get(base+'/api/v1/install')).json();assert.ok(metadata.url.endsWith('/install'));assert.equal(metadata.store_download_available,false);
  const downloadEvent=page.waitForEvent('download');await page.getByRole('link',{name:'Download QR code',exact:true}).click();const download=await downloadEvent;assert.equal(download.suggestedFilename(),'CivicSignal-360-install-QR.png');
  result.checks.push('Manifest, icon files, public address, QR image and PNG download passed');
  for(const width of [390,768,1440]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false)}
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:'artifacts/verification/mobile-install-en.png',fullPage:true});
  await page.getByRole('button',{name:'मराठी',exact:true}).click();assert.equal(await page.locator('html').getAttribute('lang'),'mr');await page.getByRole('heading',{name:'आपल्या फोनवर CivicSignal.'}).waitFor();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);await page.screenshot({path:'artifacts/verification/mobile-install-mr.png',fullPage:true});
  result.checks.push('English/Marathi and 390/768/1440 layouts passed');
  await page.getByRole('button',{name:'English',exact:true}).click();
  // Simulate the browser event contract without claiming native installation.
  await page.evaluate(()=>{const event=new Event('beforeinstallprompt',{cancelable:true});event.prompt=async()=>{};event.userChoice=Promise.resolve({outcome:'dismissed'});dispatchEvent(event)});
  await page.getByRole('button',{name:'Install app',exact:true}).click();await page.getByRole('status').filter({hasText:'Installation cancelled.'}).waitFor();assert.equal(await page.getByRole('button',{name:'Install app',exact:true}).count(),0);
  result.checks.push('Dismissed installation prompt never claims installed');
  await context.route('**/api/v1/install',route=>route.fulfill({json:{url:null,shareable:false,kind:'web_app',store_download_available:false}}));
  await page.reload();await page.getByText(/Public installation link pending deployment/).waitFor();assert.equal(await page.locator('.install-qr').count(),0);
  result.checks.push('Unconfigured address offers no misleading local QR');
  assert.deepEqual(errors,[]);result.status='passed';
}catch(error){result.status='failed';result.error=error.message;throw error}
finally{await fs.writeFile('artifacts/verification/mobile-install-browser.json',JSON.stringify(result,null,2));await browser.close()}
console.log(JSON.stringify(result,null,2));
