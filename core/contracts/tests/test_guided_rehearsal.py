import copy
import json
import unittest
from pathlib import Path
from jsonschema import ValidationError
from core.contracts.guided import GUIDED, validate_probe_request, validate_probe_response
from core.contracts.validation import baseline_binding, event_binding, reference_binding, validate_record


class GuidedRehearsalTests(unittest.TestCase):
    def setUp(self):
        fixtures = json.loads((Path(__file__).resolve().parents[3]/'contracts/examples/pa_shared_v1.json').read_text())
        self.snapshot = fixtures['rehearsal_snapshot']
        self.command = dict(record_type='RehearsalProbeCommand', schema_version='1.0',
            session_id=self.snapshot['session_id'], idempotency_key='probe-test',
            expected_state_version=self.snapshot['state_version'],
            reference=reference_binding(self.snapshot['active_reference']),
            baseline=baseline_binding(self.snapshot['active_baseline']),
            event=event_binding(self.snapshot['incident']), mode='instrument', instrument_id='guitar')

    def test_instrument_full_band_and_idle_shapes(self):
        for mode, instrument in [('instrument','guitar'),('full_band',None),('idle',None)]:
            item=dict(self.command,mode=mode,instrument_id=instrument)
            validate_probe_request(item,self.snapshot)
            item['instrument_id']=None if mode=='instrument' else 'guitar'
            with self.assertRaises(ValidationError): validate_record(item,GUIDED)

    def test_stale_binding_and_live_are_rejected(self):
        for key,value in [('expected_state_version',999),('reference',None),('session_id','other')]:
            with self.assertRaises(ValueError): validate_probe_request(dict(self.command,**{key:value}),self.snapshot)
        live=copy.deepcopy(self.snapshot)
        live['session_mode']='live'
        with self.assertRaises(ValueError): validate_probe_request(self.command,live)

    def test_selection_is_not_a_measurement_payload(self):
        for key in ('active','gain_db','confidence','accepted_baseline'):
            with self.assertRaises(ValidationError): validate_record(dict(self.command,**{key:True}),GUIDED)

    def test_response_binds_authoritative_snapshot_and_probe(self):
        response=dict(record_type='RehearsalProbeResponse',schema_version='1.0',
            command=dict(record_type='CommandResponse',schema_version='1.0',session_id=self.snapshot['session_id'],
                idempotency_key='probe-test',outcome='applied',http_status=200,snapshot=self.snapshot,error=None),
            probe=dict(record_type='RehearsalProbeState',schema_version='1.0',session_id=self.snapshot['session_id'],
                state_version=self.snapshot['state_version'],mode='instrument',instrument_id='guitar',
                probe_id='probe-1',not_before_monotonic_s=100.0))
        validate_probe_response(response)
        response['probe']['state_version']+=1
        with self.assertRaises(ValueError): validate_probe_response(response)


if __name__=='__main__': unittest.main()
