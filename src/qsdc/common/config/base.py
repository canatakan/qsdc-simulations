from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..random import RandomSource

Fraction = Annotated[float, Field(ge=0.0, le=1.0)]
NonNegative = Annotated[float, Field(ge=0.0)]
Positive = Annotated[float, Field(gt=0.0)]
PositiveInt = Annotated[int, Field(ge=1)]
NonNegativeInt = Annotated[int, Field(ge=0)]


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Fixed(Config):
    kind: Literal["fixed"] = "fixed"
    value: float

    def sample(self, rng: RandomSource) -> float:
        return self.value

    def __str__(self) -> str:
        return f"{self.value:g}"


class Uniform(Config):
    kind: Literal["uniform"] = "uniform"
    lower: float
    upper: float

    @model_validator(mode="after")
    def _ordered(self) -> Uniform:
        if self.lower > self.upper:
            raise ValueError("lower must not exceed upper")

        return self

    def sample(self, rng: RandomSource) -> float:
        return rng.uniform(self.lower, self.upper)

    def __str__(self) -> str:
        return f"U[{self.lower:g}, {self.upper:g}]"


Distribution = Annotated[Union[Fixed, Uniform], Field(discriminator="kind")]
