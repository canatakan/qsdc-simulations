import pytest

from srikara.simulator.backends import AnalyticBackend
from srikara.simulator.core.config import (
    ProtocolConfig,
    resolve_config,
    validate_config,
)
from srikara.simulator.core.distributions import FixedSqueezeR, UniformSqueezeR


def test_resolve_config_uses_backend_default_tolerance_sigmas():
    resolved = resolve_config(
        ProtocolConfig(n_states=4, tolerance_sigmas=None),
        AnalyticBackend(),
        message_count=1,
    )

    assert resolved.tolerance_sigmas == AnalyticBackend.default_tolerance_sigmas


def test_resolve_config_keeps_explicit_tolerance_sigmas():
    resolved = resolve_config(
        ProtocolConfig(n_states=4, tolerance_sigmas=0.25),
        AnalyticBackend(),
        message_count=1,
    )

    assert resolved.tolerance_sigmas == 0.25


def test_config_validation_rejects_invalid_protocol_shape():
    with pytest.raises(ValueError, match="divisible by 4"):
        validate_config(ProtocolConfig(n_states=6), message_count=1)

    with pytest.raises(ValueError, match="expected 2"):
        validate_config(ProtocolConfig(n_states=8), message_count=1)

    with pytest.raises(ValueError, match="tolerance_sigmas"):
        validate_config(
            ProtocolConfig(n_states=4, tolerance_sigmas=-1.0),
            message_count=1,
        )


def test_config_accepts_typed_squeeze_distribution():
    config = ProtocolConfig(n_states=4, squeeze_r_distribution=FixedSqueezeR(0.25))
    resolved = resolve_config(config, AnalyticBackend(), message_count=1)

    assert resolved.squeeze_r_distribution == FixedSqueezeR(0.25)


def test_squeeze_distribution_validation_rejects_invalid_ranges():
    with pytest.raises(ValueError, match="invalid squeezing range"):
        UniformSqueezeR(0.5, 0.1)

    with pytest.raises(ValueError, match="non-negative"):
        FixedSqueezeR(-0.1)
