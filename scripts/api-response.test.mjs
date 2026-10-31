import {test,afterEach} from 'node:test';
import assert from 'node:assert/strict';
import {api,ApiError} from '../apps/web/src/api.ts';
const original=globalThis.fetch;
afterEach(()=>{globalThis.fetch=original});
test('aborting after response headers never publishes a fake successful payload',async()=>{
  const abort=new DOMException('Cancelled by navigation','AbortError');
  globalThis.fetch=async()=>({ok:true,json:async()=>{throw abort}});
  await assert.rejects(api('/operations/queue'),error=>error===abort);
});
test('unreadable success cannot acknowledge a complaint or replace a queue',async()=>{
  globalThis.fetch=async()=>({ok:true,json:async()=>{throw new SyntaxError('Incomplete response')}});
  await assert.rejects(api('/reports',{method:'POST',body:'{}'}),error=>error instanceof ApiError&&error.status===502);
});
test('server conflicts keep their status for safe retry review',async()=>{
  globalThis.fetch=async()=>({ok:false,status:409,json:async()=>({detail:'Version changed'})});
  await assert.rejects(api('/cases/example/transition'),error=>error instanceof ApiError&&error.status===409&&error.message==='Version changed');
});
