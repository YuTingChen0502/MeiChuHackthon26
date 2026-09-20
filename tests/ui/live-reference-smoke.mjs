// Actual UI adapter + Runtime HTTP/WS. Only the isolated test harness supplies audio.
import assert from 'node:assert/strict';
import {RuntimeAdapter} from '../../apps/ui/runtime-adapter.js';
import {commandFor} from '../../apps/ui/app.js';
import {currentSourceFrame,logicalMicrophones,perceptionPresentation} from '../../apps/ui/live-reference.js';
const base=process.env.SMOKE_BASE;
assert.ok(base,'Run via live_reference_smoke.py');
globalThis.location=new URL(base);
const nativeFetch=globalThis.fetch;
globalThis.fetch=(url,options)=>nativeFetch(new URL(url,base),options);
let events=0,connected=false;
const adapter=new RuntimeAdapter({onSnapshot(){events++;},onStatus(){},onConnection:value=>connected=value});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function wait(predicate,label){
 const end=Date.now()+6000;
 while(Date.now()<end){if(predicate(adapter.snapshot))return adapter.snapshot;await sleep(30);}
 throw Error(`${label}: ${JSON.stringify(adapter.snapshot)}`);
}
async function scenario(value){const r=await fetch('/__ui_test/scenario',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(value)});assert.ok(r.ok);}
let key=0;
async function action(name,payload={}){await adapter.refresh(adapter.activeSessionId);return adapter.command(commandFor(adapter.snapshot,name,payload,`new-policy-smoke-${++key}`));}
try{
 assert.equal((await adapter.health()).example_only,true);
 const inventory=await adapter.audioDevices(),microphones=logicalMicrophones(inventory);
 const micA=microphones.find(x=>x.label.startsWith('Desk microphone'))?.id,micB=microphones.find(x=>x.label==='USB microphone')?.id;
 assert.ok(micA&&micB);
 const reference=new File([await (await fetch('/__ui_test/reference.wav')).arrayBuffer()],'synthetic-reference.wav',{type:'audio/wav'});
 const setup=await adapter.setupLiveReference({project:'UI integration',song:'Fake reference-target loop',families:['guitar','bass','drums'],reference,source:'uploaded_file',sourceId:'reference-asset'});
 assert.equal(setup.workflow_policy,'live_reference_v1');assert.equal(setup.active_baseline,null);
 const sid=setup.session_id,referenceId=setup.active_reference.reference_id;
 await wait(s=>connected&&currentSourceFrame(s),'file current frame');
 assert.equal(adapter.snapshot.latest_frame.example_only,true);
 await scenario({guitar:4});await wait(s=>s.incident_state==='active','file anomaly');
 await action('start_adjustment');await scenario({guitar:0});
 const aid=adapter.snapshot.adjustment.adjustment_id;
 await action('complete_adjustment',{adjustment_id:aid});await action('recheck',{adjustment_id:aid});
 await wait(s=>s.latest_verification?.outcome==='recovered','fresh verification');
 assert.equal(adapter.snapshot.latest_verification.baseline_id,null);
 const before=adapter.snapshot;
 const switching=commandFor(before,'switch_microphone',{microphone_id:micB,expected_source_generation:before.capture.source_generation},'switch-replay');
 const accepted=await adapter.command(switching);assert.equal(accepted.snapshot.capture.switch_result,'pending');assert.equal(accepted.snapshot.latest_frame,null);
 assert.deepEqual(await adapter.command(switching),accepted);
 await wait(s=>s.capture.switch_result==='applied'&&currentSourceFrame(s),'injected microphone applied');
 assert.equal(adapter.snapshot.session_id,sid);assert.equal(adapter.snapshot.active_reference.reference_id,referenceId);
 assert.equal(adapter.snapshot.latest_verification,null);assert.notEqual(adapter.snapshot.source.clock_id,before.source.clock_id);
 const p=adapter.snapshot.perception.find(p=>p.family==='bass');
 assert.equal(p.state,'detected');assert.equal(p.action_abstained,true);assert.equal(p.numerical_advice_allowed,false);
 assert.match(perceptionPresentation(adapter.snapshot,p).label,/Detected/);
 assert.equal(perceptionPresentation(adapter.snapshot,p).numeric,false);
 assert.notEqual(p.calibration_status,'calibrated');
 await scenario({fail:['mic-a']});
 await action('switch_microphone',{microphone_id:micA,expected_source_generation:adapter.snapshot.capture.source_generation});
 await wait(s=>s.capture.switch_result==='rolled_back'&&currentSourceFrame(s),'failed switch rollback');
 assert.equal(adapter.snapshot.capture.logical_microphone_id,micB);assert.equal(adapter.snapshot.capture.requested_microphone_id,micA);
 await scenario({});await action('pause');
 await action('switch_microphone',{microphone_id:micA,expected_source_generation:adapter.snapshot.capture.source_generation});
 await wait(s=>s.capture.state==='paused'&&s.capture.switch_result==='applied','paused selection');
 await action('resume');await wait(s=>currentSourceFrame(s),'resume');
 const oldCursor=adapter.cursor,oldSocket=adapter.socket;oldSocket.close();
 await wait(s=>adapter.socket!==oldSocket&&connected&&adapter.cursor>oldCursor&&currentSourceFrame(s),'WS reconnect');
 await action('stop');assert.equal(adapter.snapshot.capture.state,'stopped');
 const legacy=await adapter.request('/sessions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({song_id:setup.song.song_id,reference_id:referenceId,source:{input_kind:'uploaded_file',input_asset_or_device_id:before.source.input_asset_or_device_id},capture_fingerprint:{device_id:before.source.input_asset_or_device_id,profile_id:'legacy-ui-smoke',native_sample_rate_hz:48000,channels:1,gain_setting:null,enhancements_verified_disabled:null,geometry_id:null,provenance:'unverified'}})});
 await adapter.openSession(legacy.session_id);assert.notEqual(adapter.snapshot.workflow_policy,'live_reference_v1');
 const reused=await adapter.createLiveReferenceSession({song_id:setup.song.song_id,reference_id:referenceId});
 assert.notEqual(reused.session_id,sid);assert.equal(reused.active_reference.reference_id,referenceId);
 await wait(s=>currentSourceFrame(s),'reused reference');await action('stop');
 assert.ok(events>8);
 console.log(JSON.stringify({result:'PASS',scope:'actual UI adapter + new-policy HTTP/WS + Fake + injected PCM; no physical/model claim',events,flow:'setup/file/reference-target anomaly/adjustment/recheck/recovered/mic switch/idempotency/rollback/paused selection/resume/reconnect/stop/legacy reference reuse'}));
}finally{adapter.stopEvents();}
