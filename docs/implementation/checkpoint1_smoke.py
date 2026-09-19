import sys, os, json, tempfile, threading, socket, time, subprocess, urllib.request, base64
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path.cwd() / 'tests/integration'))
import uvicorn
from apps.api import RuntimeAPI
from apps.api.transport import create_app
from core.audio import MicAudioInput
from core.runtime import FakeEvidenceSpec
from test_api_service import wav_bytes, Clock

NODE = r'''
import { pathToFileURL } from 'node:url';
import { createInterface } from 'node:readline';
const root = process.cwd();
const base = process.env.SMOKE_BASE;
setTimeout(() => process.exit(2), 15000).unref();
const NativeWebSocket = globalThis.WebSocket;
let receivedEvents = 0;
globalThis.WebSocket = class extends NativeWebSocket {
 constructor(url) { super(url); this.addEventListener('message', () => receivedEvents++); }
};
globalThis.location = new URL(base);
const originalFetch = globalThis.fetch;
globalThis.fetch = (url, options) => originalFetch(new URL(url, base), options);
const {RuntimeAdapter} = await import(pathToFileURL(root + '/apps/ui/runtime-adapter.js'));
const {commandFor, balanceText} = await import(pathToFileURL(root + '/apps/ui/app.js'));
const adapter = new RuntimeAdapter({onSnapshot(){}, onStatus(){}, onConnection(){}});
await adapter.health();
const reference = new File([Buffer.from(process.env.SMOKE_WAV,'base64')], 'opaque-reference.wav', {type:'audio/wav'});
const s = await adapter.setup({project:'Integration smoke',song:'Synthetic checkpoint',families:['guitar','bass','drums'],reference,source:'live_microphone',sourceId:'mic-test',captureProfile:'simulated',geometryId:'test-only'});
console.log(JSON.stringify({ready:true,session_id:s.session_id}));
let count=0;
for await (const line of createInterface({input:process.stdin})) {
 const msg=JSON.parse(line);
 if(msg.action==='quit'){adapter.stopEvents();console.log(JSON.stringify({done:true,receivedEvents}));break;}
 try {
  await adapter.refresh(s.session_id);
  if(msg.action==='snapshot'){console.log(JSON.stringify({snapshot:adapter.snapshot, card:adapter.snapshot.latest_frame ? balanceText(adapter.snapshot.latest_frame.instruments[0]):null}));continue;}
  const result=await adapter.command(commandFor(adapter.snapshot,msg.action,msg.payload??{},'integration-smoke-'+(++count)));
  console.log(JSON.stringify(result));
 }catch(error){console.log(JSON.stringify({error:error.message,status:error.status,payload:error.payload}));}
}
process.exit(0);
'''
clock=Clock()
with tempfile.TemporaryDirectory(prefix='pa-checkpoint1-smoke-') as directory:
 api=RuntimeAPI(storage_dir=directory,window_size_samples=10,hop_size_samples=10,available_audio_devices={'mic-test'},monotonic_clock=clock)
 with socket.socket() as probe:
  probe.bind(('127.0.0.1',0)); port=probe.getsockname()[1]
 server=uvicorn.Server(uvicorn.Config(create_app(api),host='127.0.0.1',port=port,workers=1,loop='asyncio',http='h11',ws='websockets-sansio',log_level='error'))
 thread=threading.Thread(target=server.run,daemon=True);thread.start()
 deadline=time.time()+5
 while not server.started and time.time()<deadline:time.sleep(.02)
 assert server.started
 base=f'http://127.0.0.1:{port}'
 try:
  for resource in ['/apps/ui/','/apps/ui/app.js','/apps/ui/runtime-adapter.js']:
   with urllib.request.urlopen(base+resource,timeout=5) as response: assert response.status==200
  env=dict(os.environ,SMOKE_BASE=base,SMOKE_WAV=base64.b64encode(wav_bytes([.1]*20)).decode())
  process=subprocess.Popen(['node','--input-type=module','-e',NODE],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
  def receive():
   line=process.stdout.readline()
   if not line:raise RuntimeError('Node terminated: '+process.stderr.read())
   return json.loads(line)
  ready=receive();assert ready['ready'];sid=ready['session_id'];session=api.runtime_session(sid)
  def request(action,payload=None):
   process.stdin.write(json.dumps({'action':action,'payload':payload or {}})+'\n');process.stdin.flush()
   response=receive()
   if action not in ('snapshot','quit'):assert response.get('outcome')=='applied',response
   return response
  def observe(run,start,gain):
   clock.value=start+1
   session.analyzer.queue(FakeEvidenceSpec(deltas_db={'guitar':gain,'bass':0,'drums':0}))
   source=MicAudioInput(input_asset_or_device_id='mic-test',clock_id=session.source['clock_id'],sample_rate_hz=10,samples=[.1]*10,origin_monotonic_s=start)
   window=next(api.pipeline.iter_windows(source,session_id=sid,analysis_run_id=run))
   session.observe_window(window);return window
  def adjustment(prefix,at):
   response=request('start_adjustment');aid=response['snapshot']['adjustment']['adjustment_id']
   clock.value=at-1;request('complete_adjustment',{'adjustment_id':aid});request('recheck',{'adjustment_id':aid})
   window=observe(prefix+'-corrected',at,0)
   final=request('snapshot')['snapshot'];assert final['latest_verification']['outcome']=='recovered'
   return window,final
  observe('rehearsal-a',2,4);observe('rehearsal-b',3,4)
  snap=request('snapshot');assert snap['snapshot']['incident_state']=='active';assert '+4.0' in snap['card']
  window,final=adjustment('rehearsal',12);assert final['latest_frame']['baseline_id'] is None
  interval={k:getattr(window,k) for k in ('analysis_run_id','clock_id','sample_rate_hz','sample_start','sample_end')}
  accepted=request('accept_baseline',{'interval':interval,'accepted_by':'smoke-human','reference_difference_accepted':True,'acceptance_note':'Explicit synthetic smoke acceptance'})
  baseline=accepted['snapshot']['active_baseline'];assert baseline['immutable'];assert accepted['snapshot']['latest_frame'] is None
  request('start_live');observe('live-a',20,4);observe('live-b',21,4)
  assert request('snapshot')['snapshot']['incident_state']=='active'
  _,final=adjustment('live',32);assert final['session_mode']=='live';assert final['active_baseline']==baseline
  assert final['latest_frame']['baseline_id']==baseline['baseline_id']
  assert final['latest_verification']['first_evidence_sample_start_monotonic_s']>=final['latest_verification']['adjustment_completed_monotonic_s']+.5
  finished=request('quit');assert finished['receivedEvents']>0,finished
  process.stdin.close();process.wait(timeout=5);assert process.returncode==0
  print(json.dumps({'result':'PASS','scope':'real UI adapter + HTTP/WS + SQLite + worker-hook Fake audio; no physical or ML accuracy claim','flow':'upload/reference job/rehearsal anomaly/adjustment/recheck/accept baseline/live anomaly/adjustment/fresh verification','final_state':final['song']['workflow_state']}))
 finally:
  if 'process' in locals() and process.poll() is None:process.kill();process.wait()
  server.should_exit=True;thread.join(5)
  assert not thread.is_alive(),'server failed to stop'
