from __future__ import annotations

from qsdc.common.configuration import Parameter, ParameterSet, Validators


SIMULATOR_PARAMETERS = ParameterSet([
    Parameter(
        name="gaussian_variance",
        default=4.0,
        validator=Validators.positive_number,
    ),
    Parameter(
        name="box_bit_length",
        default=3,
        validator=Validators.positive_int,
    ),
    Parameter(
        name="detection_bit_count",
        default=1,
        validator=Validators.positive_int,
    ),
    Parameter(
        name="squeeze_r",
        default=0.7,
        validator=Validators.nonnegative_number,
    ),
    Parameter(
        name="channel_check_count",
        default=8,
        validator=Validators.positive_int,
    ),
    Parameter(
        name="authentication_check_count",
        default=4,
        validator=Validators.positive_int,
    ),
    Parameter(
        name="security_threshold",
        default=2.0,
        validator=Validators.positive_number,
    ),
    Parameter(
        name="seed",
        default=11,
        validator=Validators.nonnegative_int,
    ),
    Parameter(
        name="encoding",
        default="utf-8",
        validator=Validators.nonempty_string,
    ),
])
