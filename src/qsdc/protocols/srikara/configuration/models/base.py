"""Shared foundations for Srikara configuration models."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


Probability = Annotated[float, Field(ge=0.0, le=1.0)]
NonNegativeFloat = Annotated[float, Field(ge=0.0)]
PositiveInteger = Annotated[int, Field(gt=0)]
NonNegativeInteger = Annotated[int, Field(ge=0)]


class ConfigurationModel(BaseModel):
    """Strict base model for configuration read from JSON."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        allow_inf_nan=False,
        arbitrary_types_allowed=True,
    )
