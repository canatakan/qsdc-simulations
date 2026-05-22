"""Backend implementations for the CV QSDC srikara.simulator."""

from __future__ import annotations

from srikara.simulator.backends.analytic.ideal import AnalyticBackend
from srikara.simulator.backends.base import QSDCBackend
from srikara.simulator.backends.sf.ideal import SFBackend
from srikara.simulator.backends.sf.sampled import SFSampledBackend
from srikara.simulator.core.config import DEFAULT_SAMPLED_REPETITIONS


def make_backend(
    name: str, sampled_repetitions: int = DEFAULT_SAMPLED_REPETITIONS
) -> QSDCBackend:
    if name == "analytic":
        return AnalyticBackend()
    if name == "sf":
        return SFBackend()
    if name == "sf-sampled":
        return SFSampledBackend(repetitions=sampled_repetitions)
    raise ValueError(f"unknown backend {name!r}")


__all__ = [
    "AnalyticBackend",
    "QSDCBackend",
    "SFBackend",
    "SFSampledBackend",
    "make_backend",
]
