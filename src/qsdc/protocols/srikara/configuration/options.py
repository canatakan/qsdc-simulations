from __future__ import annotations

from typing import Any

from qsdc.common.configuration import Parameter, ParameterSet
from qsdc.protocols.srikara.configuration.parsers import Parsers
from qsdc.protocols.srikara.configuration.validators import Validators
from qsdc.protocols.srikara.simulator.encoding import ENCODING_INTERVALS


OPTIMIZATION_PARAMETERS = ParameterSet([
    Parameter(
        name="intervals",
        default="default",
        choices=list(ENCODING_INTERVALS),
        validator=Validators.string,
    ),
    Parameter(
        name="check_axis_policy",
        default="random",
        choices=["random", "optimized"],
        validator=Validators.string,
    ),
    Parameter(
        name="message_axis_policy",
        default="random",
        choices=["random", "optimized"],
        validator=Validators.string,
    ),
])


SIMULATOR_PARAMETERS = ParameterSet([
    Parameter(
        name="n_states",
        default=8,
        validator=Validators.positive_int,
    ),
    Parameter(
        name="alpha_distribution",
        default={"kind": "uniform_square", "bound": 2.0},
        validator=Validators.alpha_distribution,
        parser=Parsers.alpha_distribution,
    ),
    Parameter(
        name="squeeze_r_distribution",
        default={"kind": "uniform", "lower": 0.115, "upper": 0.576},
        validator=Validators.squeeze_r_distribution,
        parser=Parsers.squeeze_r_distribution,
    ),
    Parameter(
        name="theta_distribution",
        default={"kind": "uniform", "lower_pi": 0.0, "upper_pi": 2.0},
        validator=Validators.theta_distribution,
        parser=Parsers.theta_distribution,
    ),
    Parameter(
        name="tolerance_sigmas",
        default=1.0,
        validator=Validators.nonnegative_number,
    ),
    Parameter(
        name="seed",
        default=11,
        validator=Validators.nonnegative_int,
    ),
])


RUN_PARAMETERS = ParameterSet([
    Parameter(
        name="backend",
        default="sf-sampled",
        choices=["analytic", "sf", "sf-sampled"],
        validator=Validators.string,
    ),
    Parameter(
        name="random_source",
        default="classical",
        choices=["classical", "sf-bs-qrng"],
        validator=Validators.string,
    ),
])


BENCHMARK_PARAMETERS = ParameterSet([
    Parameter(
        name="name",
        default="benchmark",
        validator=Validators.nonempty_string,
    ),
    Parameter(
        name="payload_bit_count",
        default=4096,
        validator=Validators.positive_int,
    ),
    Parameter(
        name="trials_per_combo",
        default=1,
        validator=Validators.positive_int,
    ),
    Parameter(
        name="base_seed",
        default=0,
        validator=Validators.nonnegative_int,
    ),
    Parameter(
        name="output_dir",
        default=None,
        validator=Validators.optional_string,
    ),
    Parameter(
        name="interval_policies",
        default=["default"],
        validator=Validators.string_sequence,
    ),
    Parameter(
        name="sigma_diagnostics",
        default=False,
        validator=Validators.bool,
    ),
    Parameter(
        name="one_probabilities",
        default=[0.5],
        validator=Validators.probability_sequence,
        parser=Parsers.probability_sequence,
    ),
    Parameter(
        name="r_distributions",
        default=[{"kind": "uniform", "lower": 0.115, "upper": 0.576}],
        validator=Validators.squeeze_r_distribution_sequence,
        parser=Parsers.squeeze_r_distribution_sequence,
    ),
])


PARAMETERS = ParameterSet([
    *SIMULATOR_PARAMETERS,
    *OPTIMIZATION_PARAMETERS,
    *RUN_PARAMETERS,
    *BENCHMARK_PARAMETERS,
])


DEFAULT_OPTIONS: dict[str, Any] = PARAMETERS.defaults()
