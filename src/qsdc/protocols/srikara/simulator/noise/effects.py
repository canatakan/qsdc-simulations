"""Independent executable noise effects."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np

from qsdc.protocols.srikara.simulator.noise.base import (
    ChannelEffect,
    DetectorEffect,
    ReadoutEffect,
)


# SF uses hbar=2. The Srikara adapter reports quadratures divided by two.
VACUUM_VARIANCE = 0.25


@dataclass(frozen=True)
class PureLoss(ChannelEffect):
    """Insert a native pure-loss channel with power transmittance ``T``."""

    transmittance: float

    def apply(self, register: object) -> object:
        from strawberryfields import ops

        ops.LossChannel(self.transmittance) | register
        return register

    @property
    def amplitude_gain(self) -> float:
        return sqrt(self.transmittance)


@dataclass(frozen=True)
class ThermalLoss(ChannelEffect):
    """Insert a native thermal-loss channel."""

    transmittance: float
    environment_nbar: float

    def apply(self, register: object) -> object:
        from strawberryfields import ops

        ops.ThermalLossChannel(
            self.transmittance,
            self.environment_nbar,
        ) | register
        return register

    @property
    def amplitude_gain(self) -> float:
        return sqrt(self.transmittance)


@dataclass(frozen=True)
class DetectorInefficiency(DetectorEffect):
    """Insert detector loss immediately before homodyne measurement."""

    efficiency: float

    def apply(self, register: object) -> object:
        from strawberryfields import ops

        ops.LossChannel(self.efficiency) | register
        return register

    @property
    def amplitude_gain(self) -> float:
        return sqrt(self.efficiency)


@dataclass(frozen=True)
class ElectronicNoise(ReadoutEffect):
    """Add classical Gaussian electronic variance after SF measurement."""

    variance_snu: float

    @property
    def variance(self) -> float:
        return self.variance_snu * VACUUM_VARIANCE

    def apply(self, measured: float) -> float:
        if self.variance == 0.0:
            return measured
        return measured + float(np.random.normal(0.0, sqrt(self.variance)))
