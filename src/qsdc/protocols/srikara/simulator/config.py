"""Configuration for the CV QSDC protocol simulation."""

from __future__ import annotations

from dataclasses import dataclass

from qsdc.common.configuration import ParameterSet
from qsdc.protocols.srikara.configuration import PARAMETERS
from qsdc.protocols.srikara.simulator.distributions import (
    AlphaDistribution,
    SqueezeRDistribution,
    ThetaDistribution,
)


@dataclass(frozen=True)
class ProtocolConfig:
    n_states: int
    alpha_distribution: AlphaDistribution
    squeeze_r_distribution: SqueezeRDistribution
    theta_distribution: ThetaDistribution
    tolerance_sigmas: float
    intervals: str
    check_axis_policy: str
    message_axis_policy: str
    seed: int

    def __post_init__(self) -> None:
        type(self).parameters().validate(self)

    @classmethod
    def parameters(cls) -> ParameterSet:
        return PARAMETERS.for_fields(cls)

    @classmethod
    def from_options(cls, **overrides: object) -> "ProtocolConfig":
        return cls(**cls.parameters().options(**overrides))

    def to_dict(self) -> dict[str, object]:
        return type(self).parameters().to_dict(self)
