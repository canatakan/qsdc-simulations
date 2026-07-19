"""Parametric composition of independently configured noise stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class NoiseModel:
    """Apply ordered effects by stage name without stage-specific methods."""

    stages: Mapping[str, tuple[object, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "stages",
            {name: tuple(effects) for name, effects in self.stages.items()},
        )

    def at(self, stage: str) -> tuple[object, ...]:
        return self.stages.get(stage, ())

    def apply(self, stage: str, value: object) -> object:
        for effect in self.at(stage):
            value = effect.apply(value)
        return value

    def amplitude_gain(self, *stages: str) -> float:
        gain = 1.0
        for stage in stages:
            for effect in self.at(stage):
                gain *= effect.amplitude_gain
        return gain
