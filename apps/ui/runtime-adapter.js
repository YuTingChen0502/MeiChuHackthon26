export class RuntimeAdapter {
  constructor({ onSnapshot, onStatus, onConnection }) {
    this.onSnapshot = onSnapshot;
    this.onStatus = onStatus;
    this.onConnection = onConnection ?? (() => {});
    this.socket = null;
    this.snapshot = null;
    this.cursor = 0;
    this.activeSessionId = null;
    this.generation = 0;
    this.reconnectTimer = null;
    this.stopped = false;
    this.probe = null;
  }

  async request(path, options = {}) {
    const response = await fetch(`/v1${path}`, options);
    const payload = await response.json();
    if (!response.ok) {
      const error = new Error(payload.error?.message ?? payload.command?.error?.message ?? `Request failed (${response.status})`);
      error.status = response.status;
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  async health() { return this.request('/health'); }

  async audioDevices() { return this.request('/audio-devices'); }

  async probeState(sessionId = this.activeSessionId) {
    if (!sessionId || sessionId !== this.activeSessionId) return null;
    const probe = await this.request(`/sessions/${encodeURIComponent(sessionId)}/probes`);
    if (sessionId === this.activeSessionId) this.probe = probe;
    return probe;
  }

  async requestProbe(snapshot, mode, instrumentId = null) {
    if (snapshot.session_id !== this.activeSessionId) throw new Error('Probe does not target the active session.');
    const command = {
      record_type:'RehearsalProbeCommand', schema_version:'1.0', session_id:snapshot.session_id,
      idempotency_key:`ui-probe-${crypto.randomUUID()}`, expected_state_version:snapshot.state_version,
      reference:snapshot.active_reference && { reference_id:snapshot.active_reference.reference_id, source_asset_hash:snapshot.active_reference.source_asset_hash },
      baseline:snapshot.active_baseline && { baseline_id:snapshot.active_baseline.baseline_id, baseline_version:snapshot.active_baseline.version },
      event:snapshot.incident && { event_id:snapshot.incident.event.event_id, event_version:snapshot.incident.event_version },
      mode, instrument_id:instrumentId,
    };
    const response = await this.request(`/sessions/${encodeURIComponent(snapshot.session_id)}/probes`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(command) });
    if (response.command?.snapshot) this.acceptSnapshot(response.command.snapshot);
    this.probe = response.probe;
    return response;
  }

  async openSession(sessionId) {
    const normalized = sessionId.trim();
    if (!normalized) throw new Error('Session ID is required.');
    this.activateSession(normalized);
    try {
      const snapshot = await this.refresh(normalized);
      if (!snapshot) throw new Error('Session changed before it could be loaded.');
      await this.probeState(normalized);
      this.connect(normalized, snapshot.event_sequence);
      return snapshot;
    } catch (error) {
      if (this.activeSessionId === normalized) this.stopEvents();
      throw error;
    }
  }

  async setup(values) {
    const project = await this.request('/projects', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ name:values.project }) });
    const song = await this.request('/songs', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ project_id:project.project_id, name:values.song, instruments:values.families.map(family => ({ instrument_id:family, family })) }) });
    const asset = await this.request('/audio-assets', { method:'POST', headers:{'Content-Type':'audio/wav','X-Audio-Filename':values.reference.name}, body:values.reference });
    let job = await this.request(`/songs/${encodeURIComponent(song.song_id)}/reference`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ asset_id:asset.asset_id }) });
    while (job.status === 'queued' || job.status === 'running') {
      await new Promise(resolve => setTimeout(resolve, 150));
      job = await this.request(`/jobs/${encodeURIComponent(job.job_id)}`);
    }
    if (job.status !== 'completed') throw new Error(job.error ?? 'Reference preparation failed.');
    const sourceId = values.source === 'uploaded_file' && values.sourceId === 'reference-asset' ? asset.asset_id : values.sourceId;
    const snapshot = await this.request('/sessions', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ song_id:song.song_id, reference_id:job.reference_id, source:{ input_kind:values.source, input_asset_or_device_id:sourceId }, capture_fingerprint:{ device_id:sourceId, profile_id:values.captureProfile ?? 'ui-request-v1', native_sample_rate_hz:Number(values.requestedSampleRateHz ?? 48000), channels:1, gain_setting:null, enhancements_verified_disabled:null, geometry_id:null, provenance:'unverified' } }) });
    this.activateSession(snapshot.session_id);
    this.acceptSnapshot(snapshot);
    this.connect(snapshot.session_id, snapshot.event_sequence);
    return snapshot;
  }

  async recreateSession(previous) {
    if (!previous?.song?.song_id || !previous?.active_reference?.reference_id) throw new Error('Replacement session requires retained song and reference identities.');
    const priorCapture = previous.active_baseline?.capture;
    const sourceId = previous.source.input_asset_or_device_id;
    const snapshot = await this.request('/sessions', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({
      song_id:previous.song.song_id,
      reference_id:previous.active_reference.reference_id,
      source:{ input_kind:previous.source.input_kind, input_asset_or_device_id:sourceId },
      capture_fingerprint:{ device_id:sourceId, profile_id:priorCapture?.profile_id ?? 'ui-replacement-v1', native_sample_rate_hz:Number(priorCapture?.native_sample_rate_hz ?? 48000), channels:1, gain_setting:null, enhancements_verified_disabled:null, geometry_id:null, provenance:'unverified' },
    }) });
    this.activateSession(snapshot.session_id);
    this.acceptSnapshot(snapshot);
    this.connect(snapshot.session_id, snapshot.event_sequence);
    return snapshot;
  }

  async command(command) {
    if (command.session_id !== this.activeSessionId) throw new Error('Command does not target the active session.');
    const generation = this.generation;
    const path = command.action === 'accept_baseline' ? `/sessions/${encodeURIComponent(command.session_id)}/baseline` : `/sessions/${encodeURIComponent(command.session_id)}/actions`;
    try {
      const response = await this.request(path, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(command) });
      if (generation === this.generation) this.acceptSnapshot(response.snapshot);
      return response;
    } catch (error) {
      if (generation === this.generation && error.status === 409 && error.payload?.snapshot) this.acceptSnapshot(error.payload.snapshot);
      throw error;
    }
  }

  async refresh(sessionId, generation = this.generation) {
    if (sessionId !== this.activeSessionId || generation !== this.generation) return null;
    const snapshot = await this.request(`/sessions/${encodeURIComponent(sessionId)}`);
    if (sessionId !== this.activeSessionId || generation !== this.generation) return null;
    this.acceptSnapshot(snapshot);
    return snapshot;
  }

  activateSession(sessionId) {
    this.generation += 1;
    this.activeSessionId = sessionId;
    this.cursor = 0;
    this.snapshot = null;
    this.probe = null;
    clearTimeout(this.reconnectTimer);
    const oldSocket = this.socket;
    this.socket = null;
    oldSocket?.close();
    this.stopped = false;
    this.onConnection(false);
  }

  acceptSnapshot(snapshot) {
    if (snapshot.session_id !== this.activeSessionId) return false;
    if (this.snapshot && this.snapshot.session_id === snapshot.session_id &&
      (snapshot.event_sequence < this.snapshot.event_sequence ||
       (snapshot.event_sequence === this.snapshot.event_sequence && snapshot.state_version < this.snapshot.state_version))) return false;
    this.snapshot = snapshot;
    this.cursor = Math.max(this.cursor, snapshot.event_sequence);
    this.onSnapshot(snapshot);
    return true;
  }

  connect(sessionId, cursor) {
    if (sessionId !== this.activeSessionId) return;
    const generation = this.generation;
    this.stopped = false;
    this.socket?.close();
    this.cursor = Math.max(this.cursor, cursor);
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(`${protocol}//${location.host}/v1/sessions/${encodeURIComponent(sessionId)}/events?after_sequence=${cursor}`);
    this.socket = socket;
    socket.onopen = () => { if (this.socket === socket) { this.onConnection(true); this.onStatus('Connected to local Runtime event stream.'); } };
    socket.onmessage = event => this.handleEvent(sessionId, JSON.parse(event.data), generation);
    socket.onerror = () => this.onStatus('Runtime event stream unavailable; corrective controls are gated.');
    socket.onclose = () => {
      if (this.socket !== socket || generation !== this.generation) return;
      this.onConnection(false);
      this.onStatus('Runtime event stream disconnected; corrective controls are gated.');
      if (!this.stopped) this.reconnectTimer = setTimeout(() => this.recover(sessionId, generation), 500);
    };
  }

  async handleEvent(sessionId, event, generation = this.generation) {
    if (sessionId !== this.activeSessionId || generation !== this.generation || event.session_id !== sessionId || event.event_sequence <= this.cursor) return;
    if (event.event_sequence !== this.cursor + 1) { await this.recover(sessionId, generation); return; }
    this.cursor = event.event_sequence;
    if (event.payload?.record_type === 'SessionSnapshot') this.acceptSnapshot(event.payload);
    else await this.refresh(sessionId, generation);
  }

  async recover(sessionId, generation = this.generation) {
    try {
      await this.refresh(sessionId, generation);
      if (sessionId !== this.activeSessionId || generation !== this.generation) return;
      await this.probeState(sessionId);
      if (sessionId !== this.activeSessionId || generation !== this.generation) return;
      this.connect(sessionId, this.cursor);
      this.onStatus('Runtime event stream reconnected from an authoritative snapshot.');
    } catch {
      this.onConnection(false);
      this.onStatus('Runtime reconnect failed; corrective controls remain gated.');
      if (!this.stopped && generation === this.generation) this.reconnectTimer = setTimeout(() => this.recover(sessionId, generation), 1000);
    }
  }

  stopEvents() {
    this.stopped = true;
    clearTimeout(this.reconnectTimer);
    this.socket?.close();
  }
}
