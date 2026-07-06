from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import pi

from qsdc.protocols.srikara.simulator.distributions import (
    FixedSqueezeR,
    FixedTheta,
    UniformSqueezeR,
    UniformSquareAlpha,
    UniformTheta,
)


class Parsers:
    @staticmethod
    def probability_sequence(value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            return value
        return [float(item) for item in value]

    @staticmethod
    def alpha_distribution(value: object) -> object:
        if isinstance(value, UniformSquareAlpha):
            return value
        if not isinstance(value, Mapping):
            raise TypeError("alpha_distribution must be a config object or distribution")
        kind = value.get("kind")
        if kind == "uniform_square":
            return UniformSquareAlpha(bound=float(value["bound"]))
        raise ValueError(f"unknown alpha distribution kind {kind!r}")

    @staticmethod
    def squeeze_r_distribution(value: object) -> object:
        if isinstance(value, (UniformSqueezeR, FixedSqueezeR)):
            return value
        if not isinstance(value, Mapping):
            raise TypeError(
                "squeeze_r_distribution must be a config object or distribution"
            )
        kind = value.get("kind")
        if kind == "uniform":
            return UniformSqueezeR(
                lower=float(value["lower"]),
                upper=float(value["upper"]),
            )
        if kind == "fixed":
            return FixedSqueezeR(value=float(value["value"]))
        raise ValueError(f"unknown squeezing distribution kind {kind!r}")

    @staticmethod
    def squeeze_r_distribution_sequence(value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            return value
        return [Parsers.squeeze_r_distribution(item) for item in value]

    @staticmethod
    def theta_distribution(value: object) -> object:
        if isinstance(value, (UniformTheta, FixedTheta)):
            return value
        if not isinstance(value, Mapping):
            raise TypeError("theta_distribution must be a config object or distribution")
        kind = value.get("kind")
        if kind == "uniform":
            return UniformTheta(
                lower=float(value.get("lower_pi", 0.0)) * pi,
                upper=float(value.get("upper_pi", 2.0)) * pi,
            )
        if kind == "fixed":
            return FixedTheta(value=float(value["value_pi"]) * pi)
        raise ValueError(f"unknown theta distribution kind {kind!r}")

    @staticmethod
    def serializable_value(value: object) -> object:
        if hasattr(value, "to_dict") and callable(value.to_dict):
            return value.to_dict()
        if isinstance(value, list):
            return [Parsers.serializable_value(item) for item in value]
        if isinstance(value, tuple):
            return [Parsers.serializable_value(item) for item in value]
        if isinstance(value, dict):
            return {
                key: Parsers.serializable_value(item)
                for key, item in value.items()
            }
        return value

