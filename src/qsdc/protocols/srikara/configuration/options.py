from __future__ import annotations

from collections.abc import Callable, Iterable
from copy import deepcopy
from dataclasses import dataclass, fields
from typing import Any, Optional

from qsdc.protocols.srikara.configuration.parsers import Parsers
from qsdc.protocols.srikara.configuration.validators import Validators


ValidatorFunction = Callable[[object], bool]
ParserFunction = Callable[[object], object]


@dataclass(frozen=True)
class Parameter:
    name: str
    default: object
    validator: ValidatorFunction
    choices: Optional[list[object]] = None
    parser: Optional[ParserFunction] = None

    def validate(self, value: object) -> bool:
        if self.choices is not None and value not in self.choices:
            return False
        return self.validator(value)

    def parse(self, value: object) -> object:
        if self.parser is None:
            return value
        return self.parser(value)


class ParameterSet(list[Parameter]):
    def __init__(self, parameters: Iterable[Parameter]) -> None:
        super().__init__(parameters)

    def defaults(self) -> dict[str, object]:
        return {
            parameter.name: parameter.parse(deepcopy(parameter.default))
            for parameter in self
        }

    def default(self, name: str) -> object:
        parameter = self.parameter(name)
        return parameter.parse(deepcopy(parameter.default))

    def choices(self, name: str) -> list[object]:
        parameter = self.parameter(name)
        if parameter.choices is None:
            raise ValueError(f"option {name!r} has no choices")
        return deepcopy(parameter.choices)

    def parameter(self, name: str) -> Parameter:
        for parameter in self:
            if parameter.name == name:
                return parameter
        raise ValueError(f"unknown option {name!r}")

    def for_fields(self, config_type: type | object) -> "ParameterSet":
        return ParameterSet([
            self.parameter(field.name) for field in fields(config_type)
        ])

    def options(self, **overrides: object) -> dict[str, object]:
        options = self.defaults()
        for name, value in overrides.items():
            parameter = self.parameter(name)
            if not parameter.validate(value):
                raise ValueError(f"invalid value for option {name!r}: {value!r}")
            options[name] = parameter.parse(value)
        return options

    def validate(self, source: object) -> None:
        for parameter in self:
            value = getattr(source, parameter.name)
            if not parameter.validate(value):
                raise ValueError(
                    f"invalid value for option {parameter.name!r}: {value!r}"
                )

    def to_dict(self, source: object) -> dict[str, object]:
        return {
            parameter.name: serializable_value(getattr(source, parameter.name))
            for parameter in self
        }


def serializable_value(value: object) -> object:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if isinstance(value, list):
        return [serializable_value(item) for item in value]
    if isinstance(value, tuple):
        return [serializable_value(item) for item in value]
    if isinstance(value, dict):
        return {
            key: serializable_value(item)
            for key, item in value.items()
        }
    return value


OPTIMIZATION_PARAMETERS = ParameterSet([
    Parameter(
        name="intervals",
        default="default",
        choices=["default", "optimized"],
        validator=Validators.string,
    ),
    Parameter(
        name="check_axis_policy",
        default="random",
        choices=["random", "optimized"],
        validator=Validators.string,
    ),
    Parameter(
        name="message_axis_policy",
        default="random",
        choices=["random", "optimized"],
        validator=Validators.string,
    ),
])


SIMULATOR_PARAMETERS = ParameterSet([
    Parameter(
        name="n_states",
        default=8,
        validator=Validators.positive_int,
    ),
    Parameter(
        name="alpha_distribution",
        default={"kind": "uniform_square", "bound": 2.0},
        validator=Validators.alpha_distribution,
        parser=Parsers.alpha_distribution,
    ),
    Parameter(
        name="squeeze_r_distribution",
        default={"kind": "uniform", "lower": 0.115, "upper": 0.576},
        validator=Validators.squeeze_r_distribution,
        parser=Parsers.squeeze_r_distribution,
    ),
    Parameter(
        name="theta_distribution",
        default={"kind": "uniform", "lower_pi": 0.0, "upper_pi": 2.0},
        validator=Validators.theta_distribution,
        parser=Parsers.theta_distribution,
    ),
    Parameter(
        name="tolerance_sigmas",
        default=1.0,
        validator=Validators.nonnegative_number,
    ),
    Parameter(
        name="seed",
        default=11,
        validator=Validators.nonnegative_int,
    ),
])


BENCHMARK_PARAMETERS = ParameterSet([
    Parameter(
        name="name",
        default="benchmark",
        validator=Validators.nonempty_string,
    ),
    Parameter(
        name="backend",
        default="sf-sampled",
        choices=["analytic", "sf", "sf-sampled"],
        validator=Validators.string,
    ),
    Parameter(
        name="random_source",
        default="classical",
        choices=["classical", "sf-bs-qrng"],
        validator=Validators.string,
    ),
    Parameter(
        name="payload_bit_count",
        default=4096,
        validator=Validators.positive_int,
    ),
    Parameter(
        name="trials_per_combo",
        default=1,
        validator=Validators.positive_int,
    ),
    Parameter(
        name="base_seed",
        default=0,
        validator=Validators.nonnegative_int,
    ),
    Parameter(
        name="output_dir",
        default=None,
        validator=Validators.optional_string,
    ),
    Parameter(
        name="one_probabilities",
        default=[0.5],
        validator=Validators.probability_sequence,
        parser=Parsers.probability_sequence,
    ),
    Parameter(
        name="r_distributions",
        default=[{"kind": "uniform", "lower": 0.115, "upper": 0.576}],
        validator=Validators.squeeze_r_distribution_sequence,
        parser=Parsers.squeeze_r_distribution_sequence,
    ),
])


PARAMETERS = ParameterSet([
    *SIMULATOR_PARAMETERS,
    *OPTIMIZATION_PARAMETERS,
    *BENCHMARK_PARAMETERS,
])


DEFAULT_OPTIONS: dict[str, Any] = PARAMETERS.defaults()
