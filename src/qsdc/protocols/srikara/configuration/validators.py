from __future__ import annotations

from collections.abc import Mapping, Sequence

from qsdc.common.configuration.validators import Validators as CommonValidators
from qsdc.protocols.srikara.simulator.distributions import (
    FixedSqueezeR,
    FixedTheta,
    UniformSqueezeR,
    UniformSquareAlpha,
    UniformTheta,
)


class Validators(CommonValidators):
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
