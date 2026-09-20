import json,time
from pathlib import Path
from analyzers.separation.p1_candidate import make_p1_candidate_loader
from apps.api.config import runtime_options
from apps.api.service import RuntimeAPI
from core.audio.native import SoundDeviceBackend
from tests.integration.test_api_service import command
root=Path('.pa-runtime/canonical-live-p1-5ac8a81')
def create():
 options=runtime_options(environment={'PA_MODEL_BUNDLE':'models/candidates/nano4-p1-adapted-mvp-v1'},loader=make_p1_candidate_loader(cache_dir=root/'context-cache',candidate_mode=True,device='cpu'))
 return RuntimeAPI(storage_dir=root,window_size_samples=176400,hop_size_samples=44100,analysis_sample_rate_hz=44100,native_backend=SoundDeviceBackend(),managed_audio=True,**options)
def wait_calls(api,sid):
 end=time.monotonic()+60
 while time.monotonic()<end:
  s=api.get_session(sid)[1]
  active=api.runtime_session(sid).analyzer
  underlying=getattr(active,'analyzer',active)
  diagnostic=getattr(underlying,'execution_diagnostics',None)
  if diagnostic is None:
   time.sleep(.2);continue
  d=diagnostic()
  if d['model_calls_completed']>=2:return dict(snapshot=s,diagnostics=d)
  time.sleep(.2)
 raise RuntimeError('two actual model calls not completed')
api=create()
try:
 job=next(j for j in api.jobs.values() if j['status']=='completed')
 _,s=api.create_session(dict(song_id=job['song_id'],reference_id=job['reference_id'],workflow_policy='live_reference_v1'))
 sid=s['session_id'];before=wait_calls(api,sid)
finally:api.close()
for task in api.live_audio.closers.values():task.join(30)
api=create()
try:
 suspended=api.get_session(sid)[1]
 assert suspended['capture']['state']=='unavailable'
 assert suspended['latest_frame'] is None
 status,response=api.post_action(sid,command(suspended,'physical-restart-resume','resume'))
 assert status==200,(status,response)
 after=wait_calls(api,sid)
 assert before['snapshot']['active_reference']==after['snapshot']['active_reference']
 assert before['snapshot']['capture']['clock_id']!=after['snapshot']['capture']['clock_id']
 assert after['snapshot']['capture']['source_generation']>before['snapshot']['capture']['source_generation']
 report={'status':'PASS actual Windows candidate same-session restart','before':before,'suspended':suspended,'after':after,'limitations':'Execution only; no room accuracy or freshness claim.'}
 Path('.pa-runtime/canonical-live-p1-restart.json').write_text(json.dumps(report,indent=2))
 print(json.dumps({'status':report['status'],'session_id':sid}))
finally:api.close()
for task in api.live_audio.closers.values():task.join(30)

