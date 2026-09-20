// Frozen live_reference_v1 presentation. Never derive recognition from configuration or numbers.
export const LIVE_REFERENCE_POLICY = 'live_reference_v1';
export const isLiveReference = s => s?.workflow_policy === LIVE_REFERENCE_POLICY;

export function logicalMicrophones(discovery) {
  return (discovery?.microphones ?? []).map(m => ({
    id:m.microphone_id, label:`${m.name}${m.is_default === true ? ' (Default)' : ''}`,
  }));
}

export function sourceIdentity(s) {
  const c=s?.capture;
  return c ? `${s.session_id}:${c.source_generation}:${c.clock_id}:${c.analysis_run_id ?? ''}` : null;
}

export function currentSourceFrame(s) {
  const f=s?.latest_frame,c=s?.capture;
  return Boolean(isLiveReference(s) && f && c?.frame_fresh && c.state==='active' && c.switch_result!=='pending' &&
    f.session_id===s.session_id && f.clock_id===c.clock_id && f.clock_id===s.source?.clock_id &&
    f.analysis_run_id===c.analysis_run_id && f.input_kind===s.source?.input_kind &&
    f.input_asset_or_device_id===s.source?.input_asset_or_device_id &&
    f.reference_id===s.active_reference?.reference_id && f.baseline_id===null && f.baseline_version===null &&
    !f.quality?.stale && !f.quality?.dropout);
}

export function perceptionPresentation(s,p,{connected=true,fresh=true,switchPending=false}={}) {
  const current=currentSourceFrame(s)&&fresh&&connected&&!switchPending;
  // A Runtime support mask is not a claim of current detection; keep it visible.
  if (p?.state==='unsupported') return {state:'unsupported',label:'Unsupported',numeric:false};
  // Suppression is deliberately non-positive; only Runtime may emit a recognition state.
  if (!connected) return {state:'unavailable',label:'Input disconnected',numeric:false};
  const unavailableLabel={paused:'Listening paused',stopped:'Listening stopped',unavailable:'Input unavailable'}[s?.capture?.state];
  if (unavailableLabel) return {state:'unavailable',label:unavailableLabel,numeric:false};
  if (switchPending || ['switching','starting'].includes(s?.capture?.state))
    return {state:'unavailable',label:'Connecting input',numeric:false};
  const reasons=[...(p?.reason_codes??[]),...(s?.capture?.reason_codes??[]),...(s?.latest_frame?.quality?.reason_codes??[])];
  if (p?.state==='uncertain' || s?.latest_frame?.quality?.stale ||
      reasons.some(reason=>['stale_evidence','alignment_unavailable'].includes(reason)))
    return {state:'uncertain',label:'Uncertain',numeric:false,advice:'Advice withheld'};
  if (p?.state==='listening' && p.frame_id===null && s?.capture?.state==='listening')
    return {state:'listening',label:'Listening',numeric:false};
  if (!current || !p?.frame_id || p.frame_id!==s.latest_frame?.frame_id)
    return {state:'uncertain',label:'Uncertain · waiting for current audio',numeric:false,advice:'Advice withheld'};
  const stateLabel={detected:'Detected',not_heard:'Not heard',uncertain:'Uncertain',listening:'Listening'}[p.state]??'Uncertain';
  const label=p.state==='detected'&&p.calibration_status==='uncalibrated'?`${stateLabel} · uncalibrated`:stateLabel;
  const i=s.latest_frame.instruments?.find(i=>i.instrument_id===p.instrument_id);
  // Recognition is the Runtime state, even when downstream PA confidence abstains.
  // Numeric display needs separate explicit authorization AND valid public evidence.
  const numeric=p.state==='detected'&&p.numerical_advice_allowed===true&&p.action_abstained===false&&
    p.calibration_status==='calibrated'&&i?.confidence?.calibration_status==='calibrated'&&
    i?.activity==='active'&&['normal','too_loud','too_quiet'].includes(i.status)&&
    !i.confidence?.abstained&&typeof i.balance_deviation_db==='number'&&
    s.latest_frame.quality?.capture_compatible!==false&&
    !['unsupported','not_comparable'].includes(s.latest_frame.quality?.comparability);
  return {state:p.state,label,numeric:Boolean(numeric),advice:numeric?'Relative to reference':'Advice withheld'};
}

export function capturePresentation(s,discovery,{connected=true,fresh=true,switchPending=false}={}) {
  const c=s?.capture;
  if(!c)return {title:'Input status unavailable',detail:'Reconnect to the listening service.'};
  const options=logicalMicrophones(discovery),name=c.name??(s.source?.input_kind==='uploaded_file'?'Uploaded File':'Microphone');
  const requested=options.find(m=>m.id===c.requested_microphone_id)?.label??'the selected microphone';
  if(!connected)return {title:'Input disconnected',detail:'Waiting to reconnect. Previous audio is not current.'};
  // Present state outranks retained historical switch outcomes.
  if(c.state==='unavailable')return {title:'Microphone unavailable',detail:'Check the connection or choose another microphone. Your song and reference are kept.'};
  if(c.state==='stopped')return {title:`${name} · Stopped`,detail:'Listening has stopped. Your song and reference are kept.'};
  if(c.state==='paused')return {title:`${name} · Paused`,detail:'Resume listening when you are ready.'};
  if(switchPending||c.state==='switching'||c.switch_result==='pending')return {title:'Changing microphone…',detail:`Waiting for ${requested}. Acknowledgement does not mean audio is ready.`};
  if(c.switch_result==='rolled_back'&&['listening','active'].includes(c.state)){
    const waiting=c.state==='listening'||!fresh||!c.frame_fresh;
    return {title:`${name} · Restored · ${waiting?'Listening — waiting for fresh audio':'Active'}`,detail:`Couldn't use ${requested}. The previous input was restored. ${waiting?'Recognition may remain uncertain; previous advice is withheld.':'Only fresh audio can be used.'}`};
  }
  if(c.state==='active'&&!fresh)return {title:`${name} · Waiting for fresh audio`,detail:'The last observation is no longer current. Previous advice is withheld.'};
  return {title:`${name} · ${{starting:'Connecting',listening:'Listening',active:'Active',paused:'Paused',stopped:'Stopped'}[c.state]??'Unavailable'}`,detail:c.state==='paused'?'Resume listening when you are ready.':c.state==='active'?'Listening against the uploaded reference.':'Waiting for current audio. Recognition may remain uncertain.'};
}

export function liveReferenceView(s,{connected=true,fresh=true,switchPending=false,acknowledgedRecovery=null,recoveredKey=null}={}) {
  if(!isLiveReference(s))return 'LEGACY';
  if(['paused','stopped','unavailable'].includes(s.capture?.state))return 'INTERRUPTED';
  if(switchPending||s.capture?.switch_result==='pending'||s.capture?.state==='switching')return 'SWITCHING';
  if(['SUSPENDED','STOPPED','ERROR'].includes(s.song?.workflow_state)||['paused','stopped','unavailable'].includes(s.capture?.state))return 'INTERRUPTED';
  if(!connected||!fresh||!currentSourceFrame(s))return 'LISTENING';
  if(s.adjustment?.completed_monotonic_s!=null)return 'VERIFYING';
  if(s.adjustment||['active','adjusting','verifying'].includes(s.incident_state))return 'LIVE_ANOMALY';
  const verifiedPerception=s.perception?.find(p=>p.instrument_id===s.latest_verification?.instrument_id);
  if(recoveredKey&&recoveredKey!==acknowledgedRecovery&&
    perceptionPresentation(s,verifiedPerception,{connected,fresh}).numeric)return 'RECOVERED';
  return 'LISTENING';
}
