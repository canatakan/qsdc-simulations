"""Backend constructors for the Srikara simulator."""

from __future__ import annotations

from dataclasses import dataclass, field

from qsdc.protocols.srikara.simulator.backends.analytic.ideal import AnalyticBackend
from qsdc.protocols.srikara.simulator.backends.base import QSDCBackend
from qsdc.protocols.srikara.simulator.noise import NoiseModel


@dataclass(frozen=True)
class BackendConfig:
    """A fully parsed backend selection and its constructor settings."""

    name: str
    noise: NoiseModel = field(default_factory=NoiseModel)


def make_backend(config: BackendConfig) -> QSDCBackend:
    """Construct one backend from its already validated configuration."""

    name = config.name
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
    if name == "sf-noise":
        from qsdc.protocols.srikara.simulator.backends.strawberryfields.noisy import (
            SFNoiseBackend,
        )

        return SFNoiseBackend(noise=config.noise)
    raise ValueError(f"unknown backend {name!r}")


__all__ = [
    "AnalyticBackend",
    "BackendConfig",
    "QSDCBackend",
    "make_backend",
]
