// Presentation only. No audio inference, baseline mutation, or command authorization.
export function productError(error, context = 'action') {
  const raw = String(error?.payload?.error?.code ?? error?.payload?.command?.error?.code ?? error?.message ?? error ?? '');
  const detail = `${raw} ${error?.message ?? ''} ${error?.status ?? ''}`.toLowerCase();
  if (context === 'connection') return 'The listening service is unavailable. Check the connection, or explore an offline example.';
  if (/operator_paused/.test(detail)) return 'You paused listening. Resume when the band is ready.';
  if (/audio_eof|end.of.file/.test(detail)) return 'The audio file has finished. Choose another song or start a new listening session.';
  if (/capture.*fingerprint|capture.*mismatch|capture.*compatible|device_lost|portaudio|microphone.*lost|capture_dropout/.test(detail)) return 'We lost the microphone connection. Check the input before continuing.';
  if (/runtime_restart|new_session/.test(detail)) return 'Listening was interrupted. Start a new listening session to continue safely.';
  if (/409|conflict|state.version|stale.binding|invalid.run|run_id|interval.*coverage/.test(detail)) return 'This observation is no longer current. Review the refreshed audio and try again.';
  if (/stale|fresh|evidence|insufficient|coverage|comparab|probe|unqualified/.test(detail)) return 'We need fresh, comparable audio before continuing. Keep the band playing and review the next observation.';
  if (/model_unavailable|503|analy[sz]|reference.*fail/.test(detail) || context === 'reference') return "We couldn't analyze this reference. Check the audio file and analysis service, then try again.";
  if (/unsupported|out.of.envelope/.test(detail)) return 'This instrument or listening condition is not supported. No reliable advice is available.';
  if (/unresolved|adjustment/.test(detail)) return 'Finish the current adjustment and verification before continuing.';
  if (/baseline|capture.*verified|physical/.test(detail)) return 'This listening setup is not ready for reliable advice. Check the microphone setup before continuing.';
  if (/origin|connect|network|fetch|runtime|http|socket/.test(detail)) return 'The listening service is unavailable. Check the connection and try again.';
  return "We couldn't complete that step. Check the connection and try again.";
}

export function recoveryKey(s) {
  const v = s?.latest_verification;
  if (!v || v.outcome !== 'recovered' || !v.source_observable || s.adjustment ||
      !['none', 'resolved'].includes(s.incident_state) ||
      (s.incident && s.incident.event.event_id !== v.event_id) ||
      v.baseline_id !== (s.active_baseline?.baseline_id ?? null) || v.baseline_version !== (s.active_baseline?.version ?? null)) return null;
  return `${s.session_id}:${v.verification_id}:${v.baseline_id}:${v.baseline_version}`;
}

export function workflowState(s, { review = false, liveState = 'waiting', acknowledgedRecovery = null } = {}) {
  if (!s) return 'HOME';
  if (['SUSPENDED', 'STOPPED', 'ERROR'].includes(s.song?.workflow_state)) return 'INTERRUPTED';
  // Stale/disconnected evidence must never make an old recommendation actionable.
  if (['waiting', 'unavailable'].includes(liveState) && s.session_mode === 'live') return 'LIVE_NORMAL';
  if (s.adjustment?.completed_monotonic_s != null) return 'VERIFYING';
  if (s.adjustment || ['active', 'adjusting', 'verifying'].includes(s.incident_state)) return 'LIVE_ANOMALY';
  const recovered = recoveryKey(s);
  if (recovered && recovered !== acknowledgedRecovery && ['normal', 'recovered'].includes(liveState)) return 'RECOVERED';
  if (s.session_mode === 'live') return 'LIVE_NORMAL';
  return s.active_baseline || review ? 'BASELINE_CONFIRM' : 'REHEARSAL';
}

export function conciseConfidence(c) {
  if (c?.calibration_status === 'uncalibrated') return 'Uncalibrated';
  if (c?.abstained) return 'Insufficient Evidence';
  return c?.calibration_status === 'calibrated' ? 'Calibrated evidence' : 'Confidence unavailable';
}

export function verificationCopy(s, requestedKey) {
  const a = s?.adjustment, v = s?.latest_verification;
  const listening = Boolean(a && requestedKey === `${s.session_id}:${a.adjustment_id}:${v?.verification_id ?? 'none'}`);
  if (listening) return {title:'Re-listening…', listening:true};
  if (v && a && v.adjustment_id === a.adjustment_id) {
    return {title: {inconclusive:'We need another listen', partial:'Improved — not yet in range', not_recovered:'Still outside the accepted balance', recovered:'Back in range'}[v.outcome] ?? 'Verification update', listening:false};
  }
  return {title: listening ? 'Re-listening…' : 'Ready to listen again', listening};
}
