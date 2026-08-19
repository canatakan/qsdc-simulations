"""Backend constructors for the Srikara simulator."""

from __future__ import annotations

from qsdc.protocols.srikara.configuration.noise import NoiseConfig
from qsdc.protocols.srikara.simulator.backends.analytic.ideal import AnalyticBackend
from qsdc.protocols.srikara.simulator.backends.base import QSDCBackend
from qsdc.protocols.srikara.simulator.backends.strawberryfields.ideal import SFBackend
from qsdc.protocols.srikara.simulator.backends.strawberryfields.noisy import (
    SFNoiseBackend,
)
from qsdc.protocols.srikara.simulator.backends.strawberryfields.sampled import (
    SFSampledBackend,
)


def make_backend(name: str, noise: NoiseConfig | None = None) -> QSDCBackend:
    """Construct one backend from validated configuration values."""

    if name == "analytic":
        return AnalyticBackend()
    if name == "sf":
        return SFBackend()
    if name == "sf-sampled":
        return SFSampledBackend()
    if name == "sf-noise":
        return SFNoiseBackend(noise=noise or NoiseConfig())
    raise ValueError(f"unknown backend {name!r}")


__all__ = [
    "AnalyticBackend",
    "QSDCBackend",
    "make_backend",
]
