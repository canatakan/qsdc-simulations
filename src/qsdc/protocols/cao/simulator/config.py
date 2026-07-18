"""Configuration for Cao Gaussian-mapping simulations."""

from __future__ import annotations

from dataclasses import dataclass

from qsdc.common.configuration import ParameterSet
from qsdc.protocols.cao.configuration import SIMULATOR_PARAMETERS


@dataclass(frozen=True)
class MappingConfig:
    gaussian_variance: float
    box_bit_length: int
    detection_bit_count: int
    squeeze_r: float
    channel_check_count: int
    authentication_check_count: int
    security_threshold: float
    seed: int
    encoding: str

    def __post_init__(self) -> None:
        type(self).parameters().validate(self)
        if self.detection_bit_count >= self.box_bit_length:
            raise ValueError(
                "detection_bit_count must be smaller than box_bit_length"
            )

    @property
    def payload_box_bit_length(self) -> int:
        """Number of block-uniformized bits carried by each mapped box."""

        return self.box_bit_length - self.detection_bit_count

    @classmethod
    def parameters(cls) -> ParameterSet:
        return SIMULATOR_PARAMETERS.for_fields(cls)

    @classmethod
    def from_options(cls, **overrides: object) -> "MappingConfig":
        return cls(**cls.parameters().options(**overrides))

    def to_dict(self) -> dict[str, object]:
        return type(self).parameters().to_dict(self)
