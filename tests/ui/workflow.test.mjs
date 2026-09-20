import test from 'node:test';
import assert from 'node:assert/strict';
import {workflowState, recoveryKey, productError, conciseConfidence, verificationCopy} from '../../apps/ui/workflow.js';
const session=()=>({session_id:'s1',session_mode:'rehearsal',song:{workflow_state:'REHEARSAL'},incident_state:'none',active_baseline:null,adjustment:null});
const options={liveState:'normal'};
test('task states preserve explicit baseline and Live transitions',()=>{
  const s=session();assert.equal(workflowState(null),'HOME');
  assert.equal(workflowState(s,options),'REHEARSAL');
  assert.equal(workflowState(s,{...options,review:true}),'BASELINE_CONFIRM');
  s.active_baseline={baseline_id:'b',version:1};assert.equal(workflowState(s,options),'BASELINE_CONFIRM');
  s.session_mode='live';assert.equal(workflowState(s,options),'LIVE_NORMAL');
  s.incident_state='active';assert.equal(workflowState(s,options),'LIVE_ANOMALY');
  s.adjustment={adjustment_id:'a',completed_monotonic_s:null};assert.equal(workflowState(s,options),'LIVE_ANOMALY');
  s.adjustment.completed_monotonic_s=0;assert.equal(workflowState(s,options),'VERIFYING');
});
test('stale and paused states suppress active advice without mutating the snapshot',()=>{
  const s={...session(),session_mode:'live',incident_state:'active'};const before=JSON.stringify(s);
  assert.equal(workflowState(s,{liveState:'unavailable'}),'LIVE_NORMAL');assert.equal(JSON.stringify(s),before);
  for(const workflow_state of ['SUSPENDED','STOPPED','ERROR'])assert.equal(workflowState({...s,song:{workflow_state}},options),'INTERRUPTED');
});
test('recovery remains bound after Runtime clears resolved incident, and acknowledgement is presentation-only',()=>{
  const s={...session(),session_mode:'live',active_baseline:{baseline_id:'b',version:1},latest_verification:{verification_id:'v',event_id:'e',outcome:'recovered',source_observable:true,baseline_id:'b',baseline_version:1}};
  const before=structuredClone(s);assert.equal(workflowState(s,options),'RECOVERED');
  assert.equal(workflowState(s,{...options,acknowledgedRecovery:recoveryKey(s)}),'LIVE_NORMAL');assert.deepEqual(s,before);
  for(const liveState of ['unavailable','waiting','abstain','monitoring'])assert.notEqual(workflowState(s,{liveState}),'RECOVERED');
  for(const mutation of [{active_baseline:{baseline_id:'b',version:2}},{incident_state:'active'},{incident:{event:{event_id:'other'}}},{adjustment:{adjustment_id:'new'}}])assert.equal(recoveryKey({...s,...mutation}),null);
});
test('completed adjustment does not pretend verification was armed; acknowledgements are session-bound',()=>{
  const s={...session(),adjustment:{adjustment_id:'a',completed_monotonic_s:1}};
  assert.equal(verificationCopy(s,null).listening,false);
  assert.equal(verificationCopy(s,'s1:a:none').listening,true);
  assert.equal(verificationCopy(s,'s2:a:none').listening,false);
  s.latest_verification={verification_id:'v1',adjustment_id:'a',outcome:'inconclusive'};assert.equal(verificationCopy(s,'s1:a:none').listening,false);
  assert.equal(verificationCopy(s,'s1:a:v1').listening,true);
});
test('implementation failures become useful product messages without raw identifiers',()=>{
  for(const message of ['capture fingerprint mismatch','invalid run_id','HTTP 409','model_unavailable','PortAudio error','audio_eof','secret_internal_failure']){
    const copy=productError({message});assert.ok(copy.length>20);assert.ok(!copy.includes(message));
  }
  assert.match(productError('HTTP 409'),/no longer current/);
  assert.match(productError('PortAudio error'),/microphone connection/);
  assert.match(productError('model_unavailable'),/analyze this reference/);
  assert.match(productError({payload:{error:{code:'reference_audio_unavailable'}}},'reference'),/original WAV again.*existing session is kept/);
  assert.match(productError({unadoptedSessionId:'created-qa'},'reference'),/Open session created-qa.*stop it.*selected session was not changed/);
});
test('uncalibrated and abstained summaries never manufacture confidence',()=>{
  assert.equal(conciseConfidence({calibration_status:'uncalibrated',probability:.92}),'Uncalibrated');
  assert.equal(conciseConfidence({calibration_status:'calibrated',abstained:true}),'Insufficient Evidence');
});
