"""Live-reference policy helpers; legacy rehearsal behavior remains separate."""
import copy


class LiveReferencePolicy:
    @property
    def live_reference(self):
        return self.workflow_policy == "live_reference_v1"

    def _init_capture(self):
        self.capture=dict(state="starting",source_generation=0,requested_microphone_id=None,
            logical_microphone_id=None,name=None,native_device_id=None,clock_id=self.source["clock_id"],
            analysis_run_id=None,frame_fresh=False,timestamp_mode="unknown",operation_id=None,
            switch_result="none",reason_codes=[])
        self._current_masks={}
        self._current_hints={}
        self._hint_expires_monotonic_s=None
        self._switch_previous=None
        self._switch_paused=False

    def _perception(self, now=None, force_stale=False):
        capabilities=self.analyzer.capabilities()
        supported=capabilities.get("supported_families")
        attempted=capabilities.get("attempted_families")
        rows=[]
        frame=self.latest_frame
        fresh=bool(not force_stale and frame and self.capture["frame_fresh"]
            and not frame["quality"]["stale"] and not frame["quality"]["dropout"])
        states={s["instrument_id"]:s for s in frame["instruments"]} if frame else {}
        for configured in self.instrument_config["instruments"]:
            identity=configured["instrument_id"]
            raw=self._current_masks.get(identity,{})
            state=states.get(identity,{})
            confidence=state.get("confidence",{})
            reasons=list(confidence.get("reasons",[])) if fresh else list(self.capture["reason_codes"])
            if force_stale and "stale_evidence" not in reasons:reasons.append("stale_evidence")
            activity=raw.get("activity","unknown") if fresh else "unknown"
            observability=raw.get("observability","unknown") if fresh else "unknown"
            validity=raw.get("validity","invalid") if fresh else "invalid"
            calibration=confidence.get("calibration_status","uncalibrated")
            abstained=confidence.get("abstained",True) if fresh else True
            if attempted is None and supported is not None and configured["family"] not in supported:
                value="unsupported";activity="unsupported";validity="invalid";reasons=["unsupported_family"]
            elif attempted is None and supported is None:
                value="uncertain";reasons=["capabilities_unavailable"]
            elif not fresh:
                value="listening" if self.capture["state"]=="listening" and frame is None and "stale_evidence" not in reasons else "uncertain"
            elif activity=="unsupported":value="unsupported"
            elif "family_attribution_unvalidated" in raw.get("reason_codes",[]):value="uncertain"
            elif activity=="inactive":value="not_heard"
            elif activity=="active" and observability=="observable" and validity=="valid":value="detected"
            else:value="uncertain"
            hint=self._current_hints.get(identity) if fresh and value in ("detected","uncertain") else None
            if hint and (hint["evidence_frame_id"] != frame["frame_id"] or self._hint_expires_monotonic_s is None
                    or (self.monotonic_clock() if now is None else now) >= self._hint_expires_monotonic_s):hint=None
            rows.append(dict(**configured,adjustment_hint=copy.deepcopy(hint),state=value,frame_id=frame["frame_id"] if fresh else None,
                activity=activity,observability=observability,validity=validity,calibration_status=calibration,
                action_abstained=abstained,numerical_advice_allowed=bool(value=="detected" and calibration=="calibrated" and not abstained),
                reason_codes=list(dict.fromkeys(reasons))))
        return rows

    def _clear_source_evidence(self,reason):
        if self.incident is not None or self.adjustment is not None:
            self._audit("source_interrupted",dict(reason=reason,incident=copy.deepcopy(self.incident),
                adjustment=copy.deepcopy(self.adjustment),outcome="inconclusive"))
        self.incident=None;self.adjustment=None;self.incident_state="none"
        self.latest_frame=None;self.latest_verification=None;self.recommendations=[]
        self._frames.clear();self._frame_audio_hashes.clear();self._baseline_windows.clear()
        self._baseline_pcm_samples=0;self._guided_frame_ids.clear();self._current_masks={}
        self._current_hints={};self._hint_expires_monotonic_s=None
        self._incident_before_balance=None;self._verification_armed=False;self._detector.reset()
        self._cancel_probe();self.capture["frame_fresh"]=False

    def _accept_source_switch(self,command):
        from .session import SessionCommandError
        if not self.live_reference:raise SessionCommandError("legacy_source_fixed","Create a live-reference session.")
        if self.capture["switch_result"]=="pending":raise SessionCommandError("switch_in_progress","A microphone switch is pending.")
        if self.song["workflow_state"]=="STOPPED":raise SessionCommandError("session_stopped","Stopped sessions cannot switch.")
        self._switch_previous=dict(source=copy.deepcopy(self.source),capture=copy.deepcopy(self.capture),
            fingerprint=copy.deepcopy(self.capture_fingerprint))
        self._switch_paused=self.capture["state"]=="paused"
        self.capture.update(state="switching",source_generation=self.capture["source_generation"]+1,
            requested_microphone_id=command["payload"]["microphone_id"],operation_id=command["idempotency_key"],
            switch_result="pending",reason_codes=[])
        self._clear_source_evidence("source_changed")
        self._transition()

    def _live_lifecycle_command(self,action):
        from .session import SessionCommandError
        if action in ("accept_baseline","start_live"):
            raise SessionCommandError("legacy_action_unavailable","Live reference sessions do not accept baselines.")
        if action in ("pause","stop"):
            self.capture["source_generation"]+=1
            self._clear_source_evidence(action)
            self.capture.update(state="paused" if action=="pause" else "stopped",frame_fresh=False,
                switch_result="failed" if self.capture["switch_result"]=="pending" else self.capture["switch_result"],
                reason_codes=["operation_cancelled"] if self.capture["switch_result"]=="pending" else [])
        elif action=="resume":
            self._clear_source_evidence("source_reopened")
            self.capture.update(state="starting",frame_fresh=False,reason_codes=[],operation_id=None,requested_microphone_id=None,switch_result="none")
