import pytest

from qsdc.protocols.srikara.simulator.config import ProtocolConfig
from qsdc.protocols.srikara.simulator.distributions import FixedSqueezeR, UniformSqueezeR


def test_protocol_config_from_options_uses_option_defaults():
    config = ProtocolConfig.from_options(n_states=4)

    assert config.tolerance_sigmas == 1.0
    assert config.intervals == "default"
    assert config.check_axis_policy == "random"
    assert config.message_axis_policy == "random"


def test_protocol_config_from_options_keeps_explicit_tolerance_sigmas():
    config = ProtocolConfig.from_options(n_states=4, tolerance_sigmas=0.25)

    assert config.tolerance_sigmas == 0.25


def test_protocol_config_from_options_rejects_invalid_values():
    with pytest.raises(ValueError, match="tolerance_sigmas"):
        ProtocolConfig.from_options(n_states=4, tolerance_sigmas=-1.0)

    with pytest.raises(ValueError, match="intervals"):
        ProtocolConfig.from_options(n_states=4, intervals="bogus")


def test_config_accepts_typed_squeeze_distribution():
    config = ProtocolConfig.from_options(
        n_states=4,
        squeeze_r_distribution=FixedSqueezeR(0.25),
    )

    assert config.squeeze_r_distribution == FixedSqueezeR(0.25)


def test_squeeze_distribution_validation_rejects_invalid_ranges():
    with pytest.raises(ValueError, match="invalid squeezing range"):
        UniformSqueezeR(0.5, 0.1)

    with pytest.raises(ValueError, match="non-negative"):
        FixedSqueezeR(-0.1)
