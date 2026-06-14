"""Backend constructors for the Srikara simulator."""

from __future__ import annotations

from qsdc.protocols.srikara.simulator.backends.analytic.ideal import AnalyticBackend
from qsdc.protocols.srikara.simulator.backends.base import QSDCBackend


def make_backend(name: str) -> QSDCBackend:
    if name == "analytic":
        return AnalyticBackend()
    if name == "sf":
        from qsdc.protocols.srikara.simulator.backends.strawberryfields.ideal import (
            SFBackend,
        )

        return SFBackend()
    if name == "sf-sampled":
        from qsdc.protocols.srikara.simulator.backends.strawberryfields.sampled import (
            SFSampledBackend,
        )

        return SFSampledBackend()
    raise ValueError(f"unknown backend {name!r}")


__all__ = [
    "AnalyticBackend",
    "QSDCBackend",
    "make_backend",
]
