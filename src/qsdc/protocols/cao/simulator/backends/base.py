"""Backend interface for Cao Gaussian-mapping simulations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class VacuumQuadratures:
    x1: float
    p1: float
    x2: float
    p2: float


@dataclass(frozen=True)
class CorrelatedBeams:
    signal_x: float
    signal_p: float
    detection_x: float
    detection_p: float


@dataclass(frozen=True)
class ModulatedBeam:
    info_x: float
    info_p: float
    detection_x: float
    detection_p: float
    x_modulation: float
    p_modulation: float


@dataclass(frozen=True)
class JointMeasurement:
    x_message: float
    p_message: float


@dataclass(frozen=True)
class CorrelationNoise:
    delta_x: float
    delta_p: float


class GaussianMappingBackend(ABC):
    name: str

    @abstractmethod
    def prepare_correlated_beams(
        self,
        squeeze_r: float,
        vacuum: VacuumQuadratures,
    ) -> CorrelatedBeams:
        """Prepare the correlated signal and detection beams."""

    @abstractmethod
    def correlation_noise(self, beams: CorrelatedBeams) -> CorrelationNoise:
        """Return the channel-test combinations before message modulation."""

    @abstractmethod
    def modulate(
        self,
        beams: CorrelatedBeams,
        x_value: float,
        p_value: float,
    ) -> ModulatedBeam:
        """Apply Gaussian modulation to the signal beam."""

    @abstractmethod
    def measure_message(self, beam: ModulatedBeam) -> JointMeasurement:
        """Return the joint-measurement result."""
