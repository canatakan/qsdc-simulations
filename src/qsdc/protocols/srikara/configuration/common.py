from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Probability = Annotated[
    float,
    Field(ge=0.0, le=1.0, allow_inf_nan=False),
]
NonNegativeFloat = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
PositiveInteger = Annotated[int, Field(gt=0)]
NonNegativeInteger = Annotated[int, Field(ge=0)]

class ConfigModel(BaseModel):
    """Base contract for external configuration input."""

    model_config = ConfigDict(extra="forbid", frozen=True)

