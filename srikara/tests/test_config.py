import pytest

from srikara.simulator.backends import AnalyticBackend, SFSampledBackend
from srikara.simulator.core.config import (
    ProtocolConfig,
    resolve_config,
    validate_config,
    validate_sampled_repetitions,
)


def test_resolve_config_uses_backend_default_tolerance():
    resolved = resolve_config(
        ProtocolConfig(n_states=4, tolerance=None),
        AnalyticBackend(),
        message_count=1,
    )

    assert resolved.tolerance == AnalyticBackend.default_tolerance


def test_resolve_config_keeps_explicit_tolerance():
    resolved = resolve_config(
        ProtocolConfig(n_states=4, tolerance=0.25),
        SFSampledBackend(repetitions=4),
        message_count=1,
    )

    assert resolved.tolerance == 0.25


def test_config_validation_rejects_invalid_protocol_shape():
    with pytest.raises(ValueError, match="divisible by 4"):
        validate_config(ProtocolConfig(n_states=6), message_count=1)

    with pytest.raises(ValueError, match="expected 2"):
        validate_config(ProtocolConfig(n_states=8), message_count=1)

    with pytest.raises(ValueError, match="invalid squeezing range"):
        validate_config(
            ProtocolConfig(n_states=4, squeeze_r_min=0.5, squeeze_r_max=0.1),
            message_count=1,
        )

    with pytest.raises(ValueError, match="tolerance"):
        validate_config(ProtocolConfig(n_states=4, tolerance=-1.0), message_count=1)


def test_sampled_repetition_validation():
    validate_sampled_repetitions(1)

    with pytest.raises(ValueError, match="at least 1"):
        validate_sampled_repetitions(0)
