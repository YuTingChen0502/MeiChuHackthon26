// Frozen live_reference_v1 presentation. Never derive recognition from configuration or numbers.
export const LIVE_REFERENCE_POLICY = 'live_reference_v1';
export const LEGACY_RECEIPT_MAX_AGE_MS = 5000;
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

export function receiptMaxAgeMs(s) {
  const seconds=s?.analysis_timing?.receipt_max_age_s;
  return Number.isFinite(seconds)&&seconds>0?seconds*1000:LEGACY_RECEIPT_MAX_AGE_MS;
}

export function analysisTimingPresentation(s,snapshotReceivedAt,now=Date.now(),frameReceivedAt=snapshotReceivedAt) {
  const f=s?.latest_frame,t=s?.analysis_timing;
  if(!f)return null;
  const snapshotElapsed=snapshotReceivedAt===null?0:Math.max(0,(now-snapshotReceivedAt)/1000);
  const receiptElapsed=frameReceivedAt===null?null:Math.max(0,(now-frameReceivedAt)/1000);
  const serverAge=t&&Number.isFinite(t.snapshot_monotonic_s)?Math.max(0,t.snapshot_monotonic_s-f.capture_end_monotonic_s):null;
  const observationAge=serverAge===null?null:serverAge+snapshotElapsed;
  const processing=Math.max(0,f.published_monotonic_s-f.capture_end_monotonic_s);
  return {
    profile:t?.profile_id??'legacy timing',
    observation:observationAge===null?'Observation age unavailable':`Observation captured ${observationAge.toFixed(1)} s ago`,
    processing:`Published ${processing.toFixed(1)} s after capture${f.inference_wall_ms>0?` · model processing ${(f.inference_wall_ms/1000).toFixed(1)} s`:''}`,
    receipt:receiptElapsed===null?'Local receipt age unavailable':`Received ${receiptElapsed.toFixed(1)} s ago`,
  };
}

export function referenceComparisonPresentation(s) {
  const f=s?.latest_frame,reasons=(s?.perception??[]).flatMap(p=>p.reason_codes??[]);
  const unavailable=!f||f.reference_id!==s?.active_reference?.reference_id||f.quality?.comparability!=='comparable'||
    reasons.some(reason=>['matched_reference_span_unavailable','reference_context_reprepare_required','alignment_unavailable'].includes(reason));
  if(unavailable)return {available:false,title:'Reference comparison unavailable',detail:'No matching synchronized-start reference interval is available for this observation.'};
  const start=f.sample_start/f.sample_rate_hz,end=f.sample_end/f.sample_rate_hz;
  if(!Number.isFinite(start)||!Number.isFinite(end)||end<=start)return {available:false,title:'Reference comparison unavailable',detail:'The listening service did not provide a valid comparison interval.'};
  return {available:true,title:`Assumed synchronized-start interval ${start.toFixed(1)}–${end.toFixed(1)} s`,
    detail:'This is the same relative sample interval in the uploaded reference, not a recognized song position. Start, restart, and microphone changes begin again at 0 s; late entry, drift, seeking, loops, and section jumps are not aligned.'};
}

const hintScope=s=>`${sourceIdentity(s)??'none'}:${s?.latest_frame?.frame_id??'none'}`;
const hintKey=(s,p)=>`${hintScope(s)}:${p?.instrument_id??'none'}`;
const hintSignature=hint=>JSON.stringify([hint?.direction,hint?.status,hint?.basis,hint?.evidence_frame_id,hint?.expires_monotonic_s,hint?.automatic_execution,hint?.reason_codes]);

export class SnapshotClockTracker {
  constructor(){this.scope=null;this.serverNow=null;this.receivedAt=null;}
  reset(){this.scope=null;this.serverNow=null;this.receivedAt=null;}
  update(s,now=Date.now()){
    const scope=hintScope(s),serverNow=s?.analysis_timing?.snapshot_monotonic_s;
    if(scope!==this.scope){this.scope=scope;this.serverNow=null;this.receivedAt=now;}
    if(Number.isFinite(serverNow)&&(this.serverNow===null||serverNow>this.serverNow)){
      this.serverNow=serverNow;this.receivedAt=now;
    }
  }
  anchor(s){return hintScope(s)===this.scope?this.receivedAt:null;}
}

export class FrameResultDeadlineTracker {
  constructor(){this.scope=null;this.deadlineMs=null;this.timed=false;this.terminal=false;}
  reset(){this.scope=null;this.deadlineMs=null;this.timed=false;this.terminal=false;}
  update(s,now=Date.now()){
    const scope=hintScope(s),changed=scope!==this.scope;
    if(changed){this.scope=scope;this.deadlineMs=null;this.timed=false;this.terminal=false;}
    const t=s?.analysis_timing,f=s?.latest_frame;
    if(!t){return;}
    this.timed=true;
    if(this.terminal)return;
    if(!currentSourceFrame(s)||!Number.isFinite(t.snapshot_monotonic_s)||!Number.isFinite(t.result_max_age_s)||
       !Number.isFinite(f?.capture_end_monotonic_s)){this.deadlineMs=null;this.terminal=true;return;}
    const remaining=f.capture_end_monotonic_s+t.result_max_age_s-t.snapshot_monotonic_s;
    if(remaining<=0){this.deadlineMs=null;this.terminal=true;return;}
    const candidate=now+remaining*1000;
    if(changed||this.deadlineMs===null)this.deadlineMs=candidate;
    else this.deadlineMs=Math.min(this.deadlineMs,candidate);
  }
  deadline(s){return hintScope(s)===this.scope&&this.timed?this.deadlineMs:undefined;}
  hasTiming(s){return hintScope(s)===this.scope&&this.timed;}
}

export class HintDeadlineTracker {
  constructor(){this.scope=null;this.entries=new Map();}
  reset(){this.scope=null;this.entries.clear();}
  update(s,receivedAt,now=Date.now()){
    const scope=hintScope(s);
    if(scope!==this.scope){this.scope=scope;this.entries.clear();}
    if(!currentSourceFrame(s)){
      for(const p of s?.perception??[])this.entries.set(hintKey(s,p),null);
      return;
    }
    const active=new Set();
    for(const p of s?.perception??[]){
      const key=hintKey(s,p);active.add(key);const hint=p.adjustment_hint,existing=this.entries.get(key);
      if(!hint){this.entries.set(key,null);continue;}
      const signature=hintSignature(hint);
      if(existing===null)continue;
      if(existing&&existing.signature!==signature){this.entries.set(key,null);continue;}
      if(existing)continue;
      let deadlineMs=Infinity;
      if(s.analysis_timing){
        const expires=hint.expires_monotonic_s,serverNow=s.analysis_timing.snapshot_monotonic_s;
        if(!Number.isFinite(expires)||!Number.isFinite(serverNow)||expires<=serverNow){this.entries.set(key,null);continue;}
        deadlineMs=now+(expires-serverNow)*1000;
      }else if(receivedAt!==null)deadlineMs=receivedAt+LEGACY_RECEIPT_MAX_AGE_MS;
      this.entries.set(key,{signature,deadlineMs});
    }
    for(const key of this.entries.keys())if(!active.has(key))this.entries.set(key,null);
  }
  deadline(s,p){return this.entries.get(hintKey(s,p))?.deadlineMs??null;}
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
    return {state:'uncertain',label:'Uncertain',numeric:false,advice:'Advice withheld',
      detail:p?.reason_codes?.includes('partial_source_representation')?'Only part of this instrument family can be assessed.':
        p?.reason_codes?.includes('family_attribution_unvalidated')?'Instrument identification is not yet validated.':undefined};
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

// Display only an explicit current Runtime hint. Never calculate a direction or
// reinterpret this listening trial as calibrated advice, an incident or recovery.
export function adjustmentHintPresentation(s,p,{connected=true,fresh=true,switchPending=false,hintDeadlineMs=null,now=Date.now()}={}) {
  const hint=p?.adjustment_hint,q=s?.latest_frame?.quality;
  if(!connected||!fresh||switchPending||!currentSourceFrame(s)||!hint||
     (s.analysis_timing&&(hintDeadlineMs===null||now>=hintDeadlineMs))||
     !['detected','uncertain'].includes(p.state)||p.activity!=='active'||
     p.calibration_status!=='uncalibrated'||p.action_abstained!==true||p.numerical_advice_allowed!==false||
     p.observability!=='observable'||p.validity!=='valid'||
     p.frame_id!==s.latest_frame.frame_id||hint.evidence_frame_id!==p.frame_id||
     q?.capture_compatible!==true||q.comparability!=='comparable'||q.clipped_fraction!==0||
     s.latest_frame.identifiability_assumption!=='majority_active_sources_unchanged'||
     !s.latest_frame.instruments?.some(i=>i.instrument_id===p.instrument_id&&i.family===p.family)||
     hint.status!=='experimental'||hint.basis!=='relative_balance'||hint.automatic_execution!==false||
     !Array.isArray(hint.reason_codes)||!hint.reason_codes.length) return null;
  const direction={increase_level:'raising',reduce_level:'lowering'}[hint.direction];
  if(!direction)return null;
  return {title:'Experimental listening trial',
    text:`May try ${direction} this instrument, then listen again — experimental, uncalibrated.`,
    detail:'Assumes most other instruments are unchanged. Not a verified correction.'};
}

export function referenceReprepareRequired(s) {
  return isLiveReference(s)&&Boolean(s.perception?.some(p=>p.reason_codes?.includes('reference_context_reprepare_required')));
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
    return {title:`${name} · Restored · ${waiting?'Capturing audio':'Active'}`,detail:`Couldn't use ${requested}. The previous input was restored. ${waiting?'Capture is active while we wait for a completed analysis; previous advice is withheld.':'Only fresh audio can be used.'}`};
  }
  if(c.state==='active'&&!fresh)return {title:`${name} · Capturing audio`,detail:'Waiting for a completed analysis. The last completed observation is no longer current, so previous advice is withheld.'};
  return {title:`${name} · ${{starting:'Connecting',listening:'Capturing audio',active:'Active',paused:'Paused',stopped:'Stopped'}[c.state]??'Unavailable'}`,detail:c.state==='paused'?'Resume listening when you are ready.':c.state==='active'?'Listening against the uploaded reference.':c.state==='listening'?'Audio capture is active. Waiting for the listening service to publish a completed analysis.':'Waiting for current audio. Recognition may remain uncertain.'};
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
