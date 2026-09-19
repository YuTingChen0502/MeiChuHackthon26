"""Runtime guard for a production analyzer behind the unchanged evidence interface.

This adapter does not authorize empirical confidence. FrameBuilder withholds all
non-example probabilities and numeric advice until Lead-approved calibration exists.
"""
import copy
from core.contracts.validation import validate_analyzer_pair


class RealAnalyzerAdapter:
    def __init__(self, analyzer):
        self.analyzer = analyzer
        self._capabilities = copy.deepcopy(analyzer.capabilities())
        if self._capabilities.get('example_only') is not False:
            raise ValueError('production analyzer must explicitly declare example_only=False')
        model = self._capabilities.get('model', {})
        if not all(model.get(key) for key in ('model_bundle_id','frontend_id','taxonomy_id',
                                             'execution_profile_id','level_scale_id')):
            raise ValueError('production analyzer lacks exact model/profile identity')

    def capabilities(self):
        return copy.deepcopy(self._capabilities)

    def prepare_reference(self, windows, instrument_config):
        return self.analyzer.prepare_reference(windows, instrument_config)

    def analyze(self, window, context):
        if self.analyzer.capabilities() != self._capabilities:
            raise ValueError('analyzer capabilities changed; revalidate profiles in a new session')
        if context['model'] != self._capabilities['model'] or context['observation'] != window.identity():
            raise ValueError('analyzer request does not match runtime identity')
        evidence = self.analyzer.analyze(window, context)
        validate_analyzer_pair(context, evidence)
        if evidence['example_only']:
            raise ValueError('production evidence cannot use simulated calibration')
        return evidence

    def close(self):
        self.analyzer.close()
