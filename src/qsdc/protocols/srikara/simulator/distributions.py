"""Typed probability distributions used by the Srikara protocol."""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, pi
from typing import Protocol

from qsdc.common.random.base import RandomSource


class AlphaDistribution(Protocol):
    def sample(self, random_source: RandomSource) -> complex:
        ...

    def summary(self) -> str:
        ...

    def to_dict(self) -> dict[str, float | str]:
        ...


class SqueezeRDistribution(Protocol):
    def sample(self, random_source: RandomSource) -> float:
        ...

    def summary(self) -> str:
        ...

    def to_dict(self) -> dict[str, float | str]:
        ...


class ThetaDistribution(Protocol):
    def sample(self, random_source: RandomSource) -> float:
        ...

    def summary(self) -> str:
        ...

    def to_dict(self) -> dict[str, float | str]:
        ...


@dataclass(frozen=True)
class UniformSqueezeR:
    lower: float
    upper: float

    def __post_init__(self) -> None:
        if self.lower < 0 or self.upper < self.lower:
            raise ValueError("invalid squeezing range")

    def sample(self, random_source: RandomSource) -> float:
        return random_source.uniform(self.lower, self.upper)

    def summary(self) -> str:
        return f"r=uniform[{self.lower:g},{self.upper:g}]"

    def to_dict(self) -> dict[str, float | str]:
        return {"kind": "uniform", "lower": self.lower, "upper": self.upper}


@dataclass(frozen=True)
class FixedSqueezeR:
    value: float

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("squeezing value must be non-negative")

    def sample(self, random_source: RandomSource) -> float:
        return self.value

    def summary(self) -> str:
        return f"r=fixed[{self.value:g}]"

    def to_dict(self) -> dict[str, float | str]:
        return {"kind": "fixed", "value": self.value}


@dataclass(frozen=True)
class UniformTheta:
    lower: float = 0.0
    upper: float = 2.0 * pi

    def __post_init__(self) -> None:
        if self.upper < self.lower:
            raise ValueError("theta upper bound must be >= lower bound")

    def sample(self, random_source: RandomSource) -> float:
        return random_source.uniform(self.lower, self.upper)

    def summary(self) -> str:
        if isclose(self.lower, 0.0) and isclose(self.upper, 2.0 * pi):
            return "theta=uniform[0,2pi]"
        lower_pi = self.lower / pi
        upper_pi = self.upper / pi
        return f"theta=uniform[{lower_pi:g}pi,{upper_pi:g}pi]"

    def to_dict(self) -> dict[str, float | str]:
        return {
            "kind": "uniform",
            "lower_pi": self.lower / pi,
            "upper_pi": self.upper / pi,
        }


@dataclass(frozen=True)
class FixedTheta:
    value: float

    def sample(self, random_source: RandomSource) -> float:
        return self.value

    def summary(self) -> str:
        return f"theta=fixed[{self.value / pi:g}pi]"

    def to_dict(self) -> dict[str, float | str]:
        return {
            "kind": "fixed",
            "value_pi": self.value / pi,
        }


@dataclass(frozen=True)
class UniformSquareAlpha:
    bound: float

    def __post_init__(self) -> None:
        if self.bound < 0:
            raise ValueError("alpha bound must be non-negative")

    def sample(self, random_source: RandomSource) -> complex:
        return complex(
            random_source.uniform(-self.bound, self.bound),
            random_source.uniform(-self.bound, self.bound),
        )

    def summary(self) -> str:
        return f"alpha=uniform_square[bound={self.bound:g}]"

    def to_dict(self) -> dict[str, float | str]:
        return {"kind": "uniform_square", "bound": self.bound}
