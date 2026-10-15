import {test} from 'node:test';
import assert from 'node:assert/strict';
import {waterInvestigation} from '../apps/web/src/waterInvestigation.ts';

test('water review distinguishes missing quantities and never infers a fault',()=>{
  const checks=waterInvestigation({id:'case-1',domain:'water',evidence:{observed:0,expected:10}});
  assert.match(checks[0].available,/are attached/);
  assert.match(waterInvestigation({id:'case-1',domain:'water'})[0].available,/not attached/);
  assert.deepEqual(checks[0].sources,['case-1']);
  assert.match(checks[1].available,/does not establish/);
  assert.deepEqual(waterInvestigation({id:'other',domain:'electricity'}),[]);
});
test('only a dated follow-up after the latest intervention satisfies the evidence check',()=>{
  const record={id:'c',domain:'water',evidence_records:[{id:'i1',kind:'intervention',created_at:'2026-10-01T00:00:00Z'},{id:'f1',kind:'follow_up',created_at:'2026-10-02T00:00:00Z'},{id:'i2',kind:'intervention',created_at:'2026-10-03T00:00:00Z'}]};
  assert.match(waterInvestigation(record)[3].available,/No dated follow-up/);
  record.evidence_records.push({id:'f2',kind:'follow_up',created_at:'2026-10-04T00:00:00Z'});
  assert.deepEqual(waterInvestigation(record)[3].sources,['f2']);
  assert.match(waterInvestigation(record,true)[3].topic,/पाठपुरावा/);
});
