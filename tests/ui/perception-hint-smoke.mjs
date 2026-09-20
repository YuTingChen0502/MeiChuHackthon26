import assert from 'node:assert/strict';
import {RuntimeAdapter} from '../../apps/ui/runtime-adapter.js';
import {commandFor} from '../../apps/ui/app.js';
import {adjustmentHintPresentation,perceptionPresentation,referenceReprepareRequired,currentSourceFrame} from '../../apps/ui/live-reference.js';
const base=process.env.SMOKE_BASE;assert.ok(base);globalThis.location=new URL(base);
const nativeFetch=globalThis.fetch;globalThis.fetch=(url,options)=>nativeFetch(new URL(url,base),options);
let events=0,connected=false,key=0;
const adapter=new RuntimeAdapter({onSnapshot(){events++;},onStatus(){},onConnection:value=>connected=value});
async function wait(predicate,label){const end=Date.now()+6000;while(Date.now()<end){if(predicate(adapter.snapshot))return adapter.snapshot;await new Promise(r=>setTimeout(r,30));}throw Error(`${label}: ${JSON.stringify(adapter.snapshot)}`);}
async function phase(value){const r=await fetch('/__ui_test/scenario',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(value)});assert.ok(r.ok);}
async function action(name){await adapter.refresh(adapter.activeSessionId);return adapter.command(commandFor(adapter.snapshot,name,{},`hint-smoke-${++key}`));}
const guitar=s=>s.perception?.find(p=>p.family==='guitar');
try{
 const reference=new File([await (await fetch('/__ui_test/reference.wav')).arrayBuffer()],'synthetic-reference.wav',{type:'audio/wav'});
 const initial=await adapter.setupLiveReference({project:'Isolated simulated hints',song:'Simulated listening trial',families:['guitar','bass','drums'],reference,source:'uploaded_file',sourceId:'reference-asset'});
 await wait(s=>connected&&currentSourceFrame(s),'initial frame');
 await phase({trial:true,guitar:4});
 await wait(s=>guitar(s)?.adjustment_hint?.direction==='reduce_level','Runtime lowering hint');
 let s=adapter.snapshot,p=guitar(s);assert.equal(s.latest_frame.example_only,true);
 assert.equal(p.state,'uncertain');assert.equal(p.calibration_status,'uncalibrated');assert.equal(p.action_abstained,true);assert.equal(p.numerical_advice_allowed,false);
 assert.equal(perceptionPresentation(s,p).numeric,false);assert.match(adjustmentHintPresentation(s,p).text,/lowering/);
 assert.equal(s.incident,null);assert.deepEqual(s.recommendations,[]);
 for(const i of s.latest_frame.instruments){assert.equal(i.balance_deviation_db,null);assert.equal(i.confidence.probability,null);}
 await phase({guitar:-4});await wait(s=>guitar(s)?.adjustment_hint?.direction==='increase_level','Runtime raising hint');
 assert.match(adjustmentHintPresentation(adapter.snapshot,guitar(adapter.snapshot)).text,/raising/);
 await phase({guitar:0,global:6});await wait(s=>s.perception?.every(p=>p.adjustment_hint==null),'global gain no hint');
 await phase({guitar:4,global:0});await wait(s=>guitar(s)?.adjustment_hint,'hint again');
 const socket=adapter.socket;socket.close();await wait(s=>connected&&adapter.socket!==socket&&currentSourceFrame(s),'reconnect');
 await action('pause');assert.equal(adjustmentHintPresentation(adapter.snapshot,guitar(adapter.snapshot)),null);
 await action('resume');await wait(s=>guitar(s)?.adjustment_hint,'resumed current hint');
 await phase({reprepare:true});await wait(s=>referenceReprepareRequired(s),'old context reason');
 assert.equal(guitar(adapter.snapshot).adjustment_hint,null);
 await phase({reprepare:false,guitar:0});
 const oldId=adapter.activeSessionId,oldReference=adapter.snapshot.active_reference.reference_id;
 const job=await adapter.reprepareReference({song_id:initial.song.song_id,reference_id:oldReference});
 assert.notEqual(job.reference_id,oldReference);assert.equal(adapter.activeSessionId,oldId);assert.equal(adapter.snapshot.active_reference.reference_id,oldReference);
 await action('stop');const source={input_kind:initial.source.input_kind,input_asset_or_device_id:initial.source.input_asset_or_device_id};
 const fresh=await adapter.createLiveReferenceSession({song_id:initial.song.song_id,reference_id:job.reference_id,source,expectedSessionId:oldId});
 assert.notEqual(fresh.session_id,oldId);assert.equal(fresh.song.song_id,initial.song.song_id);
 const retained=await adapter.request(`/sessions/${oldId}`);assert.equal(retained.active_reference.reference_id,oldReference);assert.equal(retained.capture.state,'stopped');
 await wait(s=>currentSourceFrame(s),'new reference session');await action('stop');
 console.log(JSON.stringify({result:'PASS',events,scope:'Isolated simulated uncalibrated evidence through real Runtime HTTP/WS; no model or physical claim',flow:'lower/raise/global-null/public numeric-null/reconnect/pause/resume/reprepare reason/retained audio/new reference/explicit new session/old history retained'}));
}finally{adapter.stopEvents();}
