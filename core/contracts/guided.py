"""Companion structural/binding checks, not probe execution or inference."""
from .validation import (baseline_binding, event_binding, reference_binding,
                         require, validate_record, validate_response, validate_snapshot)

GUIDED = 'urn:pa-controller:guided-rehearsal:1.0'


def validate_probe_request(command, snapshot):
    """For a new request, after idempotency lookup; retries return recorded results."""
    validate_record(command, GUIDED, 'RehearsalProbeCommand')
    validate_snapshot(snapshot)
    require(command['session_id'] == snapshot['session_id'], 'Probe session mismatch')
    require(command['expected_state_version'] == snapshot['state_version'], 'Stale probe version')
    require(command['reference'] == reference_binding(snapshot['active_reference']), 'Stale reference')
    require(command['baseline'] == baseline_binding(snapshot['active_baseline']), 'Stale baseline')
    require(command['event'] == event_binding(snapshot['incident']), 'Stale incident')
    require(snapshot['session_mode'] == 'rehearsal' and
            snapshot['song']['workflow_state'] == 'REHEARSAL' and
            snapshot['adjustment'] is None, 'Probe requires idle rehearsal workflow')


def validate_probe_response(response):
    validate_record(response, GUIDED, 'RehearsalProbeResponse')
    command, probe = response['command'], response['probe']
    validate_response(command)
    require(command['session_id'] == probe['session_id'], 'Probe response session mismatch')
    if command['snapshot'] is not None:
        require(command['snapshot']['state_version'] == probe['state_version'], 'Probe response version mismatch')
