import pytest

from qsdc.protocols.cao.simulator.config import MappingConfig


def test_mapping_config_uses_parameter_defaults_and_overrides():
    config = MappingConfig.from_options(seed=7, gaussian_variance=8.0)

    assert config.seed == 7
    assert config.gaussian_variance == 8.0
    assert config.box_bit_length == 3
    assert config.to_dict()["security_threshold"] == 2.0


def test_mapping_config_validates_direct_construction():
    options = MappingConfig.parameters().defaults()
    options["gaussian_variance"] = 0.0

    with pytest.raises(ValueError, match="gaussian_variance"):
        MappingConfig(**options)
