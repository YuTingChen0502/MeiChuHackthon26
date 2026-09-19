"""Generation-fenced live-reference acquisition and asynchronous microphone switches."""
import copy
import threading
import time
import uuid

from core.audio import FileAudioInput
from core.audio.logical import MicrophoneInventory
from core.audio.native import NativeMicAudioInput
from core.runtime.worker import AudioWorker
from roles.pa import PASession
from .commands import CommandHandler
from .persistence import SQLiteCommandLedger


class LiveAudioController:
    def __init__(self,api):
        self.api=api
        self.scheduled_keys={}
        self.tasks={};self.cancellations={};self.operation_locks={}
        self.diagnostics={}
        self.analyzer_locks={};self.retired={};self.closers={}
        self.startup_timeout_s=max(5,api.pipeline.window_size_samples/(api.pipeline.frontend.sample_rate_hz or 48000)+3)
        self._shutdown=threading.Event()
        self._monitor=threading.Thread(target=self._watch,name="capture-status",daemon=True)
        self._monitor.start()

    def inventory(self):
        return MicrophoneInventory(self.api._native())

    def create_session(self,request):
        from .service import APIError
        api=self.api;song=api.songs.get(request["song_id"]);reference=api.references.get(request["reference_id"])
        if song is None:raise APIError(404,"unknown_song","Song does not exist.")
        if reference is None:raise APIError(409,"reference_not_ready","Reference is not ready.")
        if song["reference_id"]!=reference["reference_id"] or reference["song_id"]!=song["song_id"]:
            raise APIError(409,"reference_not_selected","Reference is not selected.")
        if api.reference_models.get(reference["reference_id"])!=api.analyzer_capabilities()["model"]:
            raise APIError(409,"incompatible_reference","Reanalyze with the exact selected model identity.")
        source=copy.deepcopy(request.get("source") or dict(input_kind="live_microphone",input_asset_or_device_id="system-default"))
        if source["input_kind"]=="uploaded_file" and source["input_asset_or_device_id"] not in api.assets:
            raise APIError(404,"unknown_audio_asset","Uploaded source is unavailable.")
        source["clock_id"]=api._id("clock")
        capture=dict(device_id=source["input_asset_or_device_id"],profile_id="unverified-live-reference",
            native_sample_rate_hz=48000,channels=1,gain_setting=None,enhancements_verified_disabled=None,
            geometry_id=None,provenance="unverified")
        sid=api._id("session");analyzer=api._new_analyzer()
        try:
            kwargs={k:v for k,v in (("monotonic_clock",api.monotonic_clock),("wall_clock",api.wall_clock)) if v is not None}
            session=PASession(session_id=sid,project_id=song["project_id"],song_id=song["song_id"],
                song_name=song["name"],instrument_config=song["instrument_config"],reference_profile=reference,
                source=source,capture_fingerprint=capture,analyzer=analyzer,workflow_policy="live_reference_v1",
                capture_runtime_verified=False,capture_profile_enforced=True,
                analysis_sample_rate_hz=api.pipeline.frontend.sample_rate_hz,**kwargs)
            session.set_persistence_callback(lambda state:api._save_session_state(sid,state))
            api._store.save_runtime_and_session(api._runtime_state_payload(),session.export_state())
        except Exception:
            analyzer.close();raise
        api.sessions[sid]=session
        api.handlers[sid]=CommandHandler(session=session,ledger=SQLiteCommandLedger(api._store,sid))
        response=session.snapshot()
        self.schedule(session,source["input_asset_or_device_id"],file_source=source["input_kind"]=="uploaded_file")
        return 201,response

    def persist(self,session):
        session._transition()
        self.api._save_session_state(session.session_id,session.export_state())

    def retire(self,sid,worker):
        # Publication is fenced before closing capture. A running model call
        # retains its resources until it can return safely.
        try:worker.stop(timeout_s=.15)
        except RuntimeError as exc:
            if str(exc)!="audio_worker_shutdown_timeout":raise
            retained=self.retired.setdefault(sid,[])
            retained[:]=[w for w in retained if any(t and t.is_alive() for t in (w._producer,w._consumer))]
            if worker not in retained:retained.append(worker)

    def close_analyzer_when_idle(self,sid):
        if sid in self.closers:return
        lock=self.analyzer_locks.setdefault(sid,threading.Lock())
        def close():
            with lock:self.api._close_session_analyzer(sid)
            self.retired.pop(sid,None)
        if lock.acquire(blocking=False):
            try:self.api._close_session_analyzer(sid)
            finally:lock.release()
        else:
            task=threading.Thread(target=close,name=f"analyzer-reap:{sid}",daemon=True)
            self.closers[sid]=task;task.start()

    def cancel(self,session):
        token=self.cancellations.get(session.session_id)
        if token:token.set()
        worker=self.api.workers.pop(session.session_id,None)
        if worker:self.retire(session.session_id,worker)

    def schedule(self,session,identity,*,file_source=False,previous=None,paused=False):
        sid=session.session_id
        old=self.cancellations.get(sid)
        if old:old.set()
        token=threading.Event();self.cancellations[sid]=token
        lock=self.operation_locks.setdefault(sid,threading.Lock())
        def run():
            with lock:
                if token.is_set() or self.api._closed:return
                self._run(session,identity,token,file_source,previous,paused)
        task=threading.Thread(target=run,name=f"source-open:{sid}",daemon=True)
        self.tasks[sid]=task;task.start()

    def current(self,session,token,generation=None):
        return (not token.is_set() and not self.api._closed and session.song["workflow_state"]!="STOPPED"
                and (generation is None or session.capture["source_generation"]==generation))

    def _run(self,session,identity,token,file_source,previous,paused):
        failures=[]
        try:
            old=self.api.workers.pop(session.session_id,None)
            if old:self.retire(session.session_id,old)
            if not self.current(session,token):return
            if session.session_id in self.api._failed_analyzers:
                replacement=self.api._new_analyzer();old_analyzer=session.analyzer;session.analyzer=replacement
                session._frame_builder.calibration_policy=getattr(replacement,"calibration_policy",None)
                old_analyzer.close();self.api._failed_analyzers.discard(session.session_id)
            inventory=None if file_source else self.inventory()
            candidates=[None] if file_source else inventory.resolve(identity)
            if not candidates:failures.append("microphone_unavailable")
            for endpoint in candidates:
                try:
                    if self._attempt(session,identity,endpoint,token,paused,file_source,inventory,False,failures):return
                except Exception as exc:
                    failures.append(f"{getattr(endpoint,'device_id',identity)}:{exc}")
                if not self.current(session,token):return
            if previous and previous["capture"]["native_device_id"]:
                # One exact previous endpoint attempt; never a different logical group.
                old_id=previous["capture"]["native_device_id"]
                inventory=self.inventory()
                endpoint=next((d for d in inventory.raw if d.device_id==old_id),None)
                if endpoint is not None:
                    try:
                        if self._attempt(session,previous["capture"]["logical_microphone_id"] or old_id,
                                endpoint,token,paused,False,inventory,True,failures):return
                    except Exception as exc:failures.append(f"rollback:{exc}")
        except Exception as exc:failures.append(str(exc))
        self.diagnostics[session.session_id]=failures[-16:]
        with session.command_transaction():
            if self.current(session,token):
                session.suspend_for_input("microphone_unavailable")
                session.capture.update(switch_result="failed" if session.capture["operation_id"] else "none",
                    reason_codes=list(dict.fromkeys(failures or ["microphone_unavailable"]))[-16:])
                self.persist(session)

    def _attempt(self,session,identity,endpoint,token,paused,file_source,inventory,rollback,failures):
        if not self.current(session,token):return False
        api=self.api;sid=session.session_id
        if file_source:
            asset=api.assets[identity];format=dict(sample_rate_hz=asset["sample_rate_hz"],channels=1)
            native_id=identity
        else:
            native_id=endpoint.device_id
            negotiate=getattr(api._native(),"negotiate",None)
            format=negotiate(device_id=native_id,sample_rate_hz=48000) if negotiate else dict(sample_rate_hz=48000,channels=1)
        clock_id="clock:"+uuid.uuid4().hex;run_id="run:"+uuid.uuid4().hex
        with session.command_transaction():
            if not self.current(session,token):return False
            session.capture["source_generation"]+=1;generation=session.capture["source_generation"]
            session._clear_source_evidence("source_opened")
            session.source=dict(input_kind="uploaded_file" if file_source else "live_microphone",
                input_asset_or_device_id=native_id,clock_id=clock_id)
            session.capture_fingerprint=dict(device_id=native_id,profile_id="unverified-live-reference",
                native_sample_rate_hz=format["sample_rate_hz"],channels=format["channels"],gain_setting=None,
                enhancements_verified_disabled=None,geometry_id=None,provenance="unverified")
            if api.pipeline.frontend.sample_rate_hz is None:
                session.analysis_sample_rate_hz=format["sample_rate_hz"]
            session.capture_runtime_verified=False
            if api.evidence_policy:
                approved=api.evidence_policy.capture(session.capture_fingerprint,model=session._model_identity,
                    source_kind=session.source["input_kind"])
                if approved:session.capture_fingerprint=approved;session.capture_runtime_verified=True
            session.capture.update(state="starting",clock_id=clock_id,analysis_run_id=run_id,
                logical_microphone_id=None if file_source else identity,name=None if file_source else inventory.name(identity),
                native_device_id=None if file_source else native_id,timestamp_mode="unknown",frame_fresh=False)
            session.song["workflow_state"]="LIVE_MONITORING";session.suspension_reasons=[]
            self.persist(session)
        if file_source:
            audio=FileAudioInput(input_asset_or_device_id=native_id,clock_id=clock_id,sample_rate_hz=format["sample_rate_hz"],
                samples=asset["samples"],clipping_blocks=asset.get("clipping_blocks"),origin_monotonic_s=session.monotonic_clock())
        else:
            audio=NativeMicAudioInput(backend=api._native(),device_id=native_id,clock_id=clock_id,
                sample_rate_hz=format["sample_rate_hz"],channels=format["channels"],clock=session.monotonic_clock,cancellation=token)
        first_frame=threading.Event()
        analyzer_lock=self.analyzer_locks.setdefault(sid,threading.Lock())
        def observe(window,quality,max_age):
            # Perception never holds the session publication lock. Switch commands
            # can fence immediately; completed old inference is discarded on reentry.
            with session.command_transaction():
                if not self.current(session,token,generation):return False
                context=session._context(window,purpose="verification" if session._verification_armed else "live",probe_instrument_id=None)
                analyzer=session.analyzer
            while not analyzer_lock.acquire(timeout=.05):
                if not self.current(session,token,generation):return False
            try:
                if not self.current(session,token,generation):return False
                if session.monotonic_clock()-window.capture_end_monotonic_s>max_age:return False
                begin=session.monotonic_clock()
                try:evidence=analyzer.analyze(window,context)
                except Exception:
                    if self.current(session,token,generation):api._failed_analyzers.add(sid)
                    raise
            finally:analyzer_lock.release()
            with session.command_transaction():
                if not self.current(session,token,generation):return False
                if not file_source and not session.capture_runtime_verified:
                    quality["capture_compatible"]=False;quality["reason_codes"].append("capture_not_runtime_verified")
                session.capture["timestamp_mode"]="sample_count" if file_source else audio.timestamp_mode
                session.observe_window(window,quality=quality,max_age_s=max_age,clock_uncertainty_s=.05 if not file_source else 0,
                    _prepared_evidence=evidence,_inference_started=begin)
                if session.capture["frame_fresh"]:first_frame.set()
        def ended(reason):
            with session.command_transaction():
                if self.current(session,token,generation):session.suspend_for_input(reason)
        worker=AudioWorker(audio_input=audio,pipeline=api.pipeline,session_id=sid,on_window=observe,on_end=ended,
            clock=session.monotonic_clock,pace_file=file_source,analysis_run_id=run_id)
        api.workers[sid]=worker
        keep=False
        try:
            if not self.current(session,token,generation):return False
            worker.start()
            deadline=time.monotonic()+self.startup_timeout_s
            while self.current(session,token,generation) and time.monotonic()<deadline:
                if worker.error:raise RuntimeError(worker.error)
                if not file_source and getattr(audio,"_next_sample",0)>0:break
                if first_frame.wait(.025):break
                if worker._finished.is_set():raise RuntimeError(worker.error or "capture_ended_before_fresh_frame")
            if not self.current(session,token,generation):return False
            if not first_frame.is_set() and not (not file_source and getattr(audio,"_next_sample",0)>0):
                raise RuntimeError("capture_startup_timeout")
            if paused:self.retire(sid,worker)
            with session.command_transaction():
                if not self.current(session,token,generation):return False
                if not paused and not session.capture["frame_fresh"]:session.capture["state"]="listening"
                if paused:
                    session._clear_source_evidence("paused")
                    session.song["workflow_state"]="SUSPENDED";session.suspension_reasons=["paused"]
                    session.capture["state"]="paused"
                session.capture.update(switch_result=("rolled_back" if rollback else "applied") if session.capture["operation_id"] else "none",
                    reason_codes=list(dict.fromkeys(failures))[-16:] if rollback else [])
                if session.capture["operation_id"] or paused:self.persist(session)
            keep=not paused
            self.diagnostics[sid]=list(failures)[-16:]
            return True
        finally:
            if not keep:
                self.retire(sid,worker)
                if api.workers.get(sid) is worker:api.workers.pop(sid,None)

    def reconcile(self,session,command,response):
        if response["outcome"]!="applied":return
        action=command["action"];sid=session.session_id
        # Cached retry responses never resurrect a historical operation.
        if action=="switch_microphone":
            if session.capture["operation_id"]==command["idempotency_key"] and session.capture["switch_result"]=="pending":
                if self.scheduled_keys.get(sid)!=command["idempotency_key"]:
                    self.scheduled_keys[sid]=command["idempotency_key"]
                    self.schedule(session,command["payload"]["microphone_id"],previous=session._switch_previous,paused=session._switch_paused)
        elif session.capture["state"] in ("paused","stopped"):
            self.cancel(session)
        elif action=="resume" and session.capture["state"]=="starting":
            task=self.tasks.get(sid)
            if task is None or not task.is_alive() or self.cancellations[sid].is_set():
                self.schedule(session,session.capture["logical_microphone_id"] or session.source["input_asset_or_device_id"],
                    file_source=session.source["input_kind"]=="uploaded_file")

    def _watch(self):
        while not self._shutdown.wait(.05):
            for sid,session in list(self.api.sessions.items()):
                if not session.live_reference:continue
                worker=self.api.workers.get(sid)
                if not worker:continue
                audio=worker.audio_input
                with session.command_transaction():
                    if (session.source["clock_id"]!=getattr(audio,"clock_id",None)
                            or session.capture["state"] in ("switching","paused","stopped","unavailable")):continue
                    stamp="sample_count" if isinstance(audio,FileAudioInput) else audio.timestamp_mode
                    changed=session.capture["timestamp_mode"]!=stamp
                    session.capture["timestamp_mode"]=stamp
                    if session.capture["state"]=="starting" and getattr(audio,"_next_sample",0)>0:
                        session.capture["state"]="listening";changed=True
                    frame=session.latest_frame
                    if frame and session.monotonic_clock()-frame["capture_end_monotonic_s"]>worker.max_age_s:
                        session.latest_frame=None;session._current_masks={};session.capture.update(frame_fresh=False,state="listening",reason_codes=["stale_evidence"])
                        session.recommendations=[];session.latest_verification=None;session._detector.reset();session._verification_armed=False;changed=True
                    if changed:self.persist(session)

    def close(self):
        self._shutdown.set()
        for token in self.cancellations.values():token.set()
        for sid,worker in list(self.api.workers.items()):
            if not self.api.sessions[sid].live_reference:continue
            self.api.workers.pop(sid,None)
            try:self.retire(sid,worker)
            except Exception as exc:self.api.close_errors.append(str(exc))
        for task in self.tasks.values():task.join(.2)
        self._monitor.join(2)
        for sid,session in self.api.sessions.items():
            if session.live_reference:self.close_analyzer_when_idle(sid)
