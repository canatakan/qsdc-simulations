from __future__ import annotations

from collections.abc import Callable, Iterable
from copy import deepcopy
from dataclasses import dataclass, fields
from typing import Optional

from qsdc.common.configuration.parsers import Parsers


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
            parameter.name: Parsers.serializable_value(getattr(source, parameter.name))
            for parameter in self
        }
