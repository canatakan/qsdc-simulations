from __future__ import annotations

from collections.abc import Mapping, Sequence

from qsdc.protocols.srikara.simulator.distributions import (
    FixedSqueezeR,
    FixedTheta,
    UniformSqueezeR,
    UniformSquareAlpha,
    UniformTheta,
)


class Validators:
    @staticmethod
    def string(value: object) -> bool:
        return isinstance(value, str)

    @staticmethod
    def nonempty_string(value: object) -> bool:
        return isinstance(value, str) and bool(value)

    @staticmethod
    def optional_string(value: object) -> bool:
        return value is None or isinstance(value, str)

    @staticmethod
    def string_sequence(value: object) -> bool:
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            return False
        return bool(value) and all(isinstance(item, str) for item in value)

    @staticmethod
    def int(value: object) -> bool:
        return isinstance(value, int) and not isinstance(value, bool)

    @staticmethod
    def positive_int(value: object) -> bool:
        return Validators.int(value) and value > 0

    @staticmethod
    def nonnegative_int(value: object) -> bool:
        return Validators.int(value) and value >= 0

    @staticmethod
    def number(value: object) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    @staticmethod
    def nonnegative_number(value: object) -> bool:
        return Validators.number(value) and value >= 0.0

    @staticmethod
    def probability(value: object) -> bool:
        return Validators.number(value) and 0.0 <= value <= 1.0

    @staticmethod
    def probability_sequence(value: object) -> bool:
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            return False
        return bool(value) and all(Validators.probability(item) for item in value)

    @staticmethod
    def alpha_distribution(value: object) -> bool:
        if isinstance(value, UniformSquareAlpha):
            return True
        return isinstance(value, Mapping) and value.get("kind") == "uniform_square"

    @staticmethod
    def squeeze_r_distribution(value: object) -> bool:
        if isinstance(value, (UniformSqueezeR, FixedSqueezeR)):
            return True
        return isinstance(value, Mapping) and value.get("kind") in {"uniform", "fixed"}

    @staticmethod
    def squeeze_r_distribution_sequence(value: object) -> bool:
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            return False
        return bool(value) and all(
            Validators.squeeze_r_distribution(item) for item in value
        )

    @staticmethod
    def theta_distribution(value: object) -> bool:
        if isinstance(value, (UniformTheta, FixedTheta)):
            return True
        return isinstance(value, Mapping) and value.get("kind") in {"uniform", "fixed"}
