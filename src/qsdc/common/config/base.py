from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from qsdc.common.random import RandomSource


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


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

    def sample(self, rng: RandomSource) -> float:
        return rng.uniform(self.lower, self.upper)

    def __str__(self) -> str:
        return f"U[{self.lower:g}, {self.upper:g}]"


Distribution = Annotated[Union[Fixed, Uniform], Field(discriminator="kind")]
