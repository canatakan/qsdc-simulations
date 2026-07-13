"""Configuration for Cao Gaussian-mapping simulations."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_SEED = 11
DEFAULT_GAUSSIAN_VARIANCE = 4.0
DEFAULT_BOX_BIT_LENGTH = 3
DEFAULT_SQUEEZE_R = 0.7
DEFAULT_CHANNEL_CHECK_COUNT = 8
DEFAULT_AUTHENTICATION_CHECK_COUNT = 4
DEFAULT_SECURITY_THRESHOLD = 2.0


@dataclass(frozen=True)
class MappingConfig:
    gaussian_variance: float = DEFAULT_GAUSSIAN_VARIANCE
    box_bit_length: int = DEFAULT_BOX_BIT_LENGTH
    squeeze_r: float = DEFAULT_SQUEEZE_R
    channel_check_count: int = DEFAULT_CHANNEL_CHECK_COUNT
    authentication_check_count: int = DEFAULT_AUTHENTICATION_CHECK_COUNT
    security_threshold: float = DEFAULT_SECURITY_THRESHOLD
    seed: int = DEFAULT_SEED
    encoding: str = "utf-8"


def validate_config(config: MappingConfig) -> None:
    if config.gaussian_variance <= 0:
        raise ValueError("gaussian_variance must be positive")
    if config.box_bit_length < 1:
        raise ValueError("box_bit_length must be positive")
    if config.squeeze_r < 0:
        raise ValueError("squeeze_r must be non-negative")
    if config.channel_check_count < 1:
        raise ValueError("channel_check_count must be positive")
    if config.authentication_check_count < 1:
        raise ValueError("authentication_check_count must be positive")
    if config.security_threshold <= 0:
        raise ValueError("security_threshold must be positive")
