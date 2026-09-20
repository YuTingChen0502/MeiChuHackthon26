import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {RuntimeAdapter} from '../../apps/ui/runtime-adapter.js';
import {commandFor,commandGuard,fixtureScenario} from '../../apps/ui/app.js';
import {logicalMicrophones,currentSourceFrame,perceptionPresentation,capturePresentation,liveReferenceView} from '../../apps/ui/live-reference.js';
const base=JSON.parse(await readFile(new URL('../../contracts/examples/pa_shared_v1.json',import.meta.url),'utf8'));
function session(){
 const s=fixtureScenario(base);s.workflow_policy='live_reference_v1';s.active_baseline=null;s.song.baseline_id=null;s.incident=null;s.incident_state='none';s.adjustment=null;s.latest_verification=null;
 const f=s.latest_frame;f.baseline_id=null;f.baseline_version=null;
 s.capture={requested_microphone_id:null,state:'active',source_generation:1,logical_microphone_id:'mic-a',name:'Stage microphone',native_device_id:'private-portaudio-id',clock_id:s.source.clock_id,analysis_run_id:f.analysis_run_id,frame_fresh:true,timestamp_mode:'sample_count',operation_id:null,switch_result:'none',reason_codes:[]};
 s.perception=f.instruments.map(i=>({instrument_id:i.instrument_id,family:i.family,state:'detected',frame_id:f.frame_id,reason_codes:[],activity:'active',observability:'observable',validity:'valid',calibration_status:'calibrated',action_abstained:false,numerical_advice_allowed:true}));
 return s;
}
test('logical inventory never exposes legacy raw endpoints or aliases',()=>{
 const d={devices:[{device_id:'portaudio:1',name:'Raw ASIO'}],microphones:[{microphone_id:'group-a',name:'Room mic',is_default:true}]};
 assert.deepEqual(logicalMicrophones(d),[{id:'group-a',label:'Room mic (Default)'}]);assert.deepEqual(logicalMicrophones({devices:d.devices}),[]);
});
test('recognition is read only from Runtime perception, never numeric/config inference',()=>{
 const s=session(),p=s.perception[0];s.latest_frame.instruments[0].balance_deviation_db=3;
 for(const state of ['not_heard','uncertain','unsupported','listening']){const result=perceptionPresentation(s,{...p,state});assert.equal(result.state,state);assert.equal(result.numeric,false);}
 assert.equal(perceptionPresentation(s,undefined).numeric,false);
 s.latest_frame.instruments[0].confidence.abstained=true;assert.equal(perceptionPresentation(s,p).numeric,false);
});

test('detected uncalibrated perception survives downstream unknown/abstention without numbers',()=>{
 const s=session(),p=s.perception[0],i=s.latest_frame.instruments[0];
 Object.assign(p,{calibration_status:'uncalibrated',action_abstained:true,numerical_advice_allowed:false});
 Object.assign(i,{status:'unknown',balance_deviation_db:null,source_level_delta_db:null,presence_probability:null});
 Object.assign(i.confidence,{calibration_status:'uncalibrated',abstained:true,probability:null});
 s.latest_frame.quality.capture_compatible=false;
 const result=perceptionPresentation(s,p);assert.equal(result.state,'detected');assert.equal(result.label,'Detected · uncalibrated');assert.equal(result.advice,'Advice withheld');assert.equal(result.numeric,false);
 assert.equal(result.probability,undefined);assert.equal(currentSourceFrame(s),true);
});

test('detection alone never permits numerical advice and masks remain explicit',()=>{
 const s=session(),p=s.perception[0];assert.equal(perceptionPresentation(s,p).numeric,true);
 for(const fields of [{numerical_advice_allowed:false},{action_abstained:true},{calibration_status:'uncalibrated'},{numerical_advice_allowed:undefined}])assert.equal(perceptionPresentation(s,{...p,...fields}).numeric,false);
 for(const state of ['unsupported','uncertain','not_heard']){const result=perceptionPresentation(s,{...p,state});assert.equal(result.state,state);assert.equal(result.numeric,false);}
 s.latest_frame=null;s.capture.state='listening';s.capture.frame_fresh=false;s.capture.switch_result='applied';const pending={...p,state:'listening',frame_id:null,calibration_status:'uncalibrated',numerical_advice_allowed:false};assert.equal(perceptionPresentation(s,pending).label,'Listening');assert.equal(currentSourceFrame(s),false);assert.equal(liveReferenceView(s),'LISTENING');assert.match(capturePresentation(s,{}).title,/Listening/);
});
test('no-frame listening is explicit and not detection; raw old-source frames are withheld',()=>{
 const s=session();assert.equal(currentSourceFrame(s),true);
 for(const field of ['analysis_run_id','clock_id','input_asset_or_device_id']){const bad=structuredClone(s);bad.latest_frame[field]='old';assert.equal(currentSourceFrame(bad),false);assert.equal(perceptionPresentation(bad,bad.perception[0]).numeric,false);}
 s.latest_frame=null;s.capture.state='listening';assert.equal(perceptionPresentation(s,{...s.perception[0],state:'listening',frame_id:null}).label,'Listening');
 assert.equal(perceptionPresentation(s,{...s.perception[0],state:'detected',frame_id:null}).numeric,false);
});
test('200 pending acknowledgement does not become successful capture or old advice',()=>{
 const s=session();s.capture.switch_result='pending';s.capture.state='switching';s.capture.requested_microphone_id='mic-b';s.capture.operation_id='switch-1';
 assert.equal(currentSourceFrame(s),false);assert.equal(liveReferenceView(s),'SWITCHING');assert.match(capturePresentation(s,{}).title,/Changing/);
 assert.equal(perceptionPresentation(s,s.perception[0]).numeric,false);
 s.capture.switch_result='rolled_back';s.capture.state='active';
 const copy=capturePresentation(s,{microphones:[{microphone_id:'mic-b',name:'Other microphone'}]});assert.match(copy.title,/Stage microphone.*Restored/);assert.match(copy.detail,/Other microphone/);
 s.capture.switch_result='failed';s.capture.state='unavailable';assert.match(capturePresentation(s,{}).title,/unavailable/);
});

test('current capture state outranks retained rollback and pending outcomes',()=>{
 const s=session();
 for(const result of ['rolled_back','pending']){
  s.capture.switch_result=result;
  for(const [state,label]of [['unavailable','unavailable'],['paused','Paused'],['stopped','Stopped']]){
   s.capture.state=state;const copy=capturePresentation(s,{});assert.match(copy.title,new RegExp(label));assert.doesNotMatch(copy.title,/Restored|Changing/);assert.equal(liveReferenceView(s),'INTERRUPTED');
  }
 }
 s.capture.switch_result='rolled_back';s.capture.state='listening';assert.match(capturePresentation(s,{}).title,/Listening/);
 s.capture.state='active';assert.match(capturePresentation(s,{}, {fresh:false}).title,/fresh audio/);
 assert.match(capturePresentation(s,{}).title,/Restored/);
});

test('initial listening, stale or alignment uncertainty and unavailable input are distinct',()=>{
 const s=session(),p={...s.perception[0],state:'listening',frame_id:null};
 s.latest_frame=null;s.capture.state='listening';s.capture.frame_fresh=false;
 assert.equal(perceptionPresentation(s,p).label,'Listening');
 for(const reason of ['stale_evidence','alignment_unavailable']){
  const result=perceptionPresentation(s,{...p,state:'uncertain',reason_codes:[reason]});assert.equal(result.label,'Uncertain');assert.equal(result.numeric,false);
 }
 s.capture.state='unavailable';assert.equal(perceptionPresentation(s,p).label,'Input unavailable');
 const stale=session();stale.latest_frame.quality.stale=true;assert.equal(perceptionPresentation(stale,stale.perception[0]).label,'Uncertain');
 assert.equal(perceptionPresentation(session(),session().perception[0],{fresh:false}).state,'uncertain');
});

test('Runtime unsupported mask remains visible during input waiting, loss and switching',()=>{
 const s=session(),p={...s.perception[0],state:'unsupported',numerical_advice_allowed:false};
 for(const state of ['starting','listening','switching','unavailable','paused','stopped']){
  s.capture.state=state;const value=perceptionPresentation(s,p,{fresh:false});assert.equal(value.label,'Unsupported');assert.equal(value.numeric,false);
 }
 assert.equal(perceptionPresentation(s,p,{connected:false}).label,'Unsupported');
});
test('microphone switching is allowed without fresh evidence in each nonterminal workflow',()=>{
 const s=session(),adapter={snapshot:s};s.latest_frame=null;
 for(const state of ['LIVE_MONITORING','PA_ADJUSTING','VERIFY_RECOVERY','SUSPENDED']){s.song.workflow_state=state;assert.equal(commandGuard('switch_microphone','authoritative',adapter,s,true,null).allowed,true);}
 s.song.workflow_state='STOPPED';assert.equal(commandGuard('switch_microphone','authoritative',adapter,s,true,null).allowed,false);
 s.song.workflow_state='LIVE_MONITORING';s.capture.switch_result='pending';assert.equal(commandGuard('switch_microphone','authoritative',adapter,s,true,null).allowed,false);
 for(const action of ['accept_baseline','start_live'])assert.equal(commandGuard(action,'authoritative',adapter,s,true,null).allowed,false);
});
test('bound switch preserves session/reference and exact source generation',async()=>{
 const s=session(),requests=[],a=new RuntimeAdapter({onSnapshot(){},onStatus(){}});a.activateSession(s.session_id);a.acceptSnapshot(s);
 const c=commandFor(s,'switch_microphone',{microphone_id:'mic-b',expected_source_generation:1},'same-key');
 a.request=async(path,options)=>{requests.push([path,JSON.parse(options.body)]);return {outcome:'applied',snapshot:{...s,state_version:s.state_version+1,capture:{...s.capture,state:'switching',switch_result:'pending',operation_id:'same-key'}}};};
 await a.command(c);assert.equal(requests.length,1);assert.match(requests[0][0],/\/actions$/);assert.deepEqual(requests[0][1],c);assert.equal(a.snapshot.capture.state,'switching');assert.equal(a.snapshot.active_reference.reference_id,s.active_reference.reference_id);
});
test('rollback acknowledgement survives listening without promoting stale evidence',()=>{
 const s=session();s.capture.switch_result='rolled_back';s.capture.state='listening';s.capture.frame_fresh=false;s.latest_frame=null;
 for(const state of ['listening','active']){
  s.capture.state=state;const copy=capturePresentation(s,{}, {fresh:false});
  assert.match(copy.title,/Restored.*Listening.*fresh audio/);assert.match(copy.detail,/Couldn't use.*previous input was restored.*uncertain.*withheld/);
  assert.equal(perceptionPresentation(s,s.perception[0],{fresh:false}).numeric,false);
  assert.equal(liveReferenceView(s,{fresh:false}),'LISTENING');
 }
 assert.match(capturePresentation(s,{}, {connected:false}).title,/disconnected/);
 s.capture.state='switching';assert.match(capturePresentation(s,{}).title,/Changing microphone/);
 for(const state of ['unavailable','paused','stopped']){
  s.capture.state=state;assert.doesNotMatch(capturePresentation(s,{}).title,/Restored/);
 }
});

test('same-session delayed snapshots cannot restore a fenced source generation',()=>{
 const s=session(),a=new RuntimeAdapter({onSnapshot(){},onStatus(){}});a.activateSession(s.session_id);a.acceptSnapshot(s);
 const next={...s,event_sequence:s.event_sequence+1,capture:{...s.capture,source_generation:2,state:'switching'},latest_frame:null};assert.equal(a.acceptSnapshot(next),true);
 assert.equal(a.acceptSnapshot({...s,event_sequence:s.event_sequence+50}),false);assert.equal(a.snapshot.capture.source_generation,2);assert.equal(a.snapshot.latest_frame,null);
});
test('new session reuses song/reference only, omits legacy capture and model rate',async()=>{
 const s=session(),a=new RuntimeAdapter({onSnapshot(){},onStatus(){}}),requests=[];a.connect=()=>{};a.request=async(path,options)=>{requests.push([path,JSON.parse(options.body)]);return s;};
 await a.createLiveReferenceSession({song_id:s.song.song_id,reference_id:s.active_reference.reference_id});
 assert.deepEqual(requests,[['/sessions',{song_id:s.song.song_id,reference_id:s.active_reference.reference_id,workflow_policy:'live_reference_v1'}]]);
});
test('setup uploads and prepares once then creates reference-target Live even with no microphone',async()=>{
 const s=session();s.song.workflow_state='SUSPENDED';s.capture.state='unavailable';s.latest_frame=null;s.perception=[];
 const a=new RuntimeAdapter({onSnapshot(){},onStatus(){}}),requests=[];a.connect=()=>{};
 a.request=async(path,options)=>{requests.push([path,options]);if(path==='/projects')return {project_id:'p'};if(path==='/songs')return {song_id:s.song.song_id};if(path==='/audio-assets')return {asset_id:'asset'};if(path.endsWith('/reference'))return {status:'completed',reference_id:s.active_reference.reference_id,job_id:'j'};if(path==='/sessions')return s;throw Error(path);};
 await a.setupLiveReference({project:'Show',song:'Song',families:['bass'],reference:{name:'source.wav'},source:'live_microphone',sourceId:null});
 const body=JSON.parse(requests.at(-1)[1].body);assert.equal(body.workflow_policy,'live_reference_v1');assert.equal(body.capture_fingerprint,undefined);assert.equal(body.source,undefined);assert.equal(a.snapshot.capture.state,'unavailable');assert.equal(requests.filter(([p])=>p==='/audio-assets').length,1);
});

test('stale capture and disconnected perception never present positive current evidence',()=>{
 const s=session();assert.match(capturePresentation(s,{}, {fresh:false}).title,/fresh audio/);
 assert.equal(perceptionPresentation(s,s.perception[0],{fresh:false}).numeric,false);
 assert.equal(perceptionPresentation(s,s.perception[0],{connected:false}).state,'unavailable');
 assert.equal(liveReferenceView(s,{fresh:false,recoveredKey:'old-result'}),'LISTENING');
 s.capture.state='switching';assert.equal(liveReferenceView(s,{recoveredKey:'old-result'}),'SWITCHING');
});

test('recovery concerns the verified instrument and never bypasses current advice abstention',()=>{
 const s=session();s.latest_verification={instrument_id:s.perception[0].instrument_id};
 s.perception[1].state='unsupported';assert.equal(liveReferenceView(s,{recoveredKey:'verified-result'}),'RECOVERED');
 s.perception[0].action_abstained=true;assert.equal(liveReferenceView(s,{recoveredKey:'verified-result'}),'LISTENING');
});

test('stopping event observation during reconnect cannot restart the stream',async()=>{
 const s=session(),a=new RuntimeAdapter({onSnapshot(){},onStatus(){}});a.activateSession(s.session_id);a.acceptSnapshot(s);
 let resolve;a.request=()=>new Promise(r=>resolve=r);a.connect=()=>assert.fail('stopped observation restarted');
 const recovering=a.recover(s.session_id);a.stopEvents();resolve(s);await recovering;
});

test('new-policy reconnect reads current snapshot without legacy probe requests',async()=>{
 const s=session(),a=new RuntimeAdapter({onSnapshot(){},onStatus(){}}),paths=[];a.activateSession(s.session_id);a.acceptSnapshot(s);
 a.request=async path=>{paths.push(path);return {...s,event_sequence:s.event_sequence+4};};
 let cursor;a.connect=(id,value)=>{assert.equal(id,s.session_id);cursor=value;};
 await a.recover(s.session_id);assert.deepEqual(paths,[`/sessions/${s.session_id}`]);assert.equal(cursor,s.event_sequence+4);
});

test('legacy session response cannot be treated as live-reference creation',async()=>{
 const s=session(),a=new RuntimeAdapter({onSnapshot(){},onStatus(){}});delete s.workflow_policy;
 a.request=async()=>s;a.connect=()=>assert.fail('must not connect a legacy session');
 await assert.rejects(a.createLiveReferenceSession({song_id:s.song.song_id,reference_id:s.active_reference.reference_id}),/live-reference update/);
 assert.equal(a.activeSessionId,null);
});

test('new-policy command conflict refreshes source identity and retains the original failure',async()=>{
 const s=session(),a=new RuntimeAdapter({onSnapshot(){},onStatus(){}});a.activateSession(s.session_id);a.acceptSnapshot(s);
 const c=commandFor(s,'switch_microphone',{microphone_id:'mic-b',expected_source_generation:1},'conflict-key');
 const next={...s,event_sequence:s.event_sequence+1,state_version:s.state_version+1,latest_frame:null,capture:{...s.capture,source_generation:2,state:'switching',switch_result:'pending'}};
 const error=Object.assign(new Error('conflict'),{status:409,payload:{snapshot:next}});let requests=0;a.request=async()=>{requests++;throw error;};
 await assert.rejects(a.command(c),e=>e===error);assert.equal(requests,1);assert.equal(a.snapshot.capture.source_generation,2);assert.equal(a.snapshot.latest_frame,null);
});

test('late command response from a previous session cannot change the new session',async()=>{
 const s=session(),a=new RuntimeAdapter({onSnapshot(){},onStatus(){}});a.activateSession(s.session_id);a.acceptSnapshot(s);
 let resolve;a.request=()=>new Promise(r=>resolve=r);
 const pending=a.command(commandFor(s,'switch_microphone',{microphone_id:'mic-b',expected_source_generation:1},'late-key'));
 const next={...s,session_id:'new-session'};a.activateSession(next.session_id);a.acceptSnapshot(next);
 resolve({outcome:'applied',snapshot:s});await pending;assert.equal(a.snapshot.session_id,'new-session');
});

test('late socket callbacks after reconnect or session switch have no presentation effects',async()=>{
 const oldSocket=globalThis.WebSocket,oldLocation=globalThis.location,sockets=[],messages=[];
 globalThis.location={protocol:'http:',host:'localhost'};
 globalThis.WebSocket=class {constructor(){sockets.push(this);}close(){}};
 try{
  const s=session(),a=new RuntimeAdapter({onSnapshot(){},onStatus:m=>messages.push(m)});a.activateSession(s.session_id);a.acceptSnapshot(s);a.connect(s.session_id,s.event_sequence);
  const first=sockets[0];a.connect(s.session_id,s.event_sequence);first.onerror();first.onmessage({data:'not parsed from obsolete socket'});assert.equal(messages.length,0);
  a.activateSession('new-session');sockets[1].onerror();assert.equal(messages.length,0);
 }finally{globalThis.WebSocket=oldSocket;globalThis.location=oldLocation;}
});
