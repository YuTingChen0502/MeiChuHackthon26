"""Backend-neutral runtime components for the PA performance core."""

from .deviation import FrameBuilder
from .fake_analyzer import FakeEvidenceSpec, FakeInstrumentAnalyzer

__all__ = ["FakeEvidenceSpec", "FakeInstrumentAnalyzer", "FrameBuilder"]
