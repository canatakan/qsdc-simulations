"""Transfer one three-bit symbol and show its noise calculations."""

from cmath import polar
from math import exp, sqrt

import strawberryfields as sf

from qsdc.common.quadrature import QuadratureAxis
from qsdc.protocols.srikara.configuration.distribution import (
    AlphaConfig,
    UniformSqueezeConfig,
    UniformThetaConfig,
)
from qsdc.protocols.srikara.configuration.noise import (
    DelayConfig,
    DetectorInefficiencyConfig,
    ElectronicNoiseConfig,
    NoiseConfig,
    PureLossConfig,
    ThermalLossConfig,
)
from qsdc.protocols.srikara.configuration.simulator import SimulatorConfig
from qsdc.protocols.srikara.simulator.backends.strawberryfields.noisy import (
    SFNoiseBackend,
)
from qsdc.protocols.srikara.simulator.backends.strawberryfields.utils.calculations import (
    normalize_quadrature,
    normalize_quadrature_variance,
)
from qsdc.protocols.srikara.simulator.backends.strawberryfields.utils.noise import (
    Noise,
)
from qsdc.protocols.srikara.simulator.encoding import interval_for_bits
from qsdc.protocols.srikara.simulator.protocol import simulate_qsdc

BITS = "011"
VACUUM_VARIANCE = 0.25


def _moments(operations: list[object], axis: QuadratureAxis) -> tuple[float, float]:
    """Evaluate an independent diagnostic SF program built from operations."""

    program = sf.Program(1)
    with program.context as q:
        for operation in operations:
            operation | q[0]

    state = sf.Engine("gaussian").run(program).state
    if state is None:
        raise RuntimeError("diagnostic Strawberry Fields program returned no state")

    mean, variance = state.quad_expectation(0, axis.angle)
    return (
        normalize_quadrature(float(mean)),
        normalize_quadrature_variance(float(variance)),
    )


def _print_stage(
    number: int,
    title: str,
    formula: str,
    moments: tuple[float, float],
) -> None:
    mean, variance = moments
    print(
        f"{number}. {title}\n"
        f"   {formula}\n"
        f"   expected mean = {mean:.6f}\n"
        f"   expected variance = {variance:.6f}\n"
    )


def main() -> None:
    forward = PureLossConfig(transmittance=0.9)
    delay = DelayConfig(
        duration_seconds=0.5,
        lifetime_seconds=2.0,
        initial_efficiency=0.9,
        environment_nbar=0.01,
    )
    returned = ThermalLossConfig(
        transmittance=0.9,
        environment_nbar=0.02,
    )
    detector = DetectorInefficiencyConfig(efficiency=0.95)
    readout = ElectronicNoiseConfig(variance_snu=0.02)
    noise = NoiseConfig(
        forward=[forward],
        alice_delay=[delay],
        return_path=[returned],
        alice_detector=[detector],
        alice_readout=[readout],
        bob_detector=[detector],
        bob_readout=[readout],
    )
    config = SimulatorConfig(
        n_states=4,
        intervals="optimized_v8",
        alpha_distribution=AlphaConfig(bound=2.0),
        squeeze_r_distribution=UniformSqueezeConfig(lower=0.25, upper=1.0),
        theta_distribution=UniformThetaConfig(lower_pi=0.0, upper_pi=2.0),
        tolerance_sigmas=4.0,
        check_axis_policy="optimized",
        message_axis_policy="optimized",
        seed=4,
    )

    result = simulate_qsdc([BITS], config, backend=SFNoiseBackend(noise))
    message = result.messages[0]
    decoy = result.decoys[0]
    prepared = result.prepared_states[message.index]
    interval = interval_for_bits(message.sent_bits, intervals=message.intervals)
    alpha_abs, alpha_phase = polar(prepared.alpha)
    beta_abs, beta_phase = polar(message.alice_beta)

    delay_transmittance = delay.initial_efficiency * exp(
        -delay.duration_seconds / delay.lifetime_seconds
    )
    delay_environment_variance = (
        2.0 * delay.environment_nbar + 1.0
    ) * VACUUM_VARIANCE
    return_environment_variance = (
        2.0 * returned.environment_nbar + 1.0
    ) * VACUUM_VARIANCE
    readout_variance = sum(
        Noise.readout_variance(effect.variance_snu)
        for effect in noise.bob_readout
    )

    operations: list[object] = [
        sf.ops.Dgate(alpha_abs, alpha_phase),
        sf.ops.Sgate(-prepared.squeeze_r, prepared.theta),
    ]
    prepared_moments = _moments(operations, message.axis)
    operations.append(sf.ops.LossChannel(forward.transmittance))
    loss_moments = _moments(operations, message.axis)
    operations.append(sf.ops.ThermalLossChannel(delay_transmittance, delay.environment_nbar))
    delay_moments = _moments(operations, message.axis)
    before_message_operations = list(operations)
    operations.append(sf.ops.Dgate(beta_abs, beta_phase))
    encoded_moments = _moments(operations, message.axis)
    operations.append(
        sf.ops.ThermalLossChannel(returned.transmittance, returned.environment_nbar)
    )
    return_moments = _moments(operations, message.axis)
    operations.append(sf.ops.Sgate(prepared.squeeze_r, prepared.theta))
    unsqueezed_moments = _moments(operations, message.axis)
    operations.append(sf.ops.LossChannel(detector.efficiency))
    detector_moments = _moments(operations, message.axis)

    no_message_operations = before_message_operations + [
        sf.ops.Dgate(0.0, 0.0),
        sf.ops.ThermalLossChannel(returned.transmittance, returned.environment_nbar),
        sf.ops.Sgate(prepared.squeeze_r, prepared.theta),
        sf.ops.LossChannel(detector.efficiency),
    ]
    expected_baseline, _ = _moments(no_message_operations, message.axis)
    expected_measurement = detector_moments[0]
    total_variance = detector_moments[1] + readout_variance
    total_sigma = sqrt(total_variance)
    random_residual = message.measured - expected_measurement
    decoded_random_error = random_residual / message.response_factor

    print(
        f"""Noisy QSDC transfer
===================
sent bits = {message.sent_bits}
control modes = {result.control_indices}
delayed modes = {result.route.delayed_indices}
message mode = {result.message_indices}
decoy mode = {result.decoy_indices}

Control checks at Alice
-----------------------
"""
    )
    for control in result.controls:
        deviation = abs(control.measured - control.expected) / control.expected_sigma
        print(
            f"mode {control.index}: axis={control.axis.value}, "
            f"expected={control.expected:.6f}, measured={control.measured:.6f}, "
            f"sigma={control.expected_sigma:.6f}, deviation={deviation:.3f} sigma, "
            f"passed={control.passed}"
        )

    print(
        f"""
Returned decoy check at Bob
---------------------------
mode {decoy.index}: axis={decoy.axis.value}, expected={decoy.expected:.6f}, measured={decoy.measured:.6f}, sigma={decoy.expected_sigma:.6f}, passed={decoy.passed}

Message-mode noise path
-----------------------
Alice samples m = {message.message_value:.6f} from the interval [{interval.lower:g}, {interval.upper:g})
Alice displacement beta = {message.alice_beta:.6f}
Bob measures the {message.axis.value} quadrature

"""
    )
    _print_stage(
        1,
        "Bob prepares the mode",
        f"D(alpha), alpha = {prepared.alpha:.6f}, vacuum variance = {VACUUM_VARIANCE:.6f}",
        prepared_moments,
    )
    _print_stage(
        2,
        "Forward pure loss",
        f"mu' = sqrt({forward.transmittance:g}) * mu; "
        f"V' = {forward.transmittance:g} * V + (1 - {forward.transmittance:g}) * V_vacuum",
        loss_moments,
    )
    _print_stage(
        3,
        "Alice's delay storage",
        f"T_delay = {delay_transmittance:.6f}; V_environment = {delay_environment_variance:.6f}",
        delay_moments,
    )
    _print_stage(
        4,
        f"Alice encodes {message.sent_bits}",
        f"D(beta), beta = {message.alice_beta:.6f}; mean shifts by beta",
        encoded_moments,
    )
    _print_stage(
        5,
        "Thermal return loss",
        f"mu' = sqrt({returned.transmittance:g}) * mu; V_environment = {return_environment_variance:.6f}",
        return_moments,
    )
    _print_stage(
        6,
        "Bob applies inverse squeezing",
        f"Sgate({prepared.squeeze_r:.6f}, {prepared.theta:.6f})",
        unsqueezed_moments,
    )
    _print_stage(
        7,
        "Bob's detector inefficiency",
        f"V' = {detector.efficiency:g} * V + (1 - {detector.efficiency:g}) * V_vacuum",
        detector_moments,
    )
    print(
        f"""8. Electronic readout
   added_variance = variance_snu * vacuum_variance
                  = {readout.variance_snu:g} * {VACUUM_VARIANCE:g}
                  = {readout_variance:.6f}
   measured_variance = {detector_moments[1]:.6f} + {readout_variance:.6f}
                     = {total_variance:.6f}
   measured_sigma = sqrt({total_variance:.6f}) = {total_sigma:.6f}

9. Bob's actual sampled measurement and decoding
   expected noisy mean = {expected_measurement:.6f}
   sampled measurement = {message.measured:.6f}
   expected baseline without Alice's message = {expected_baseline:.6f}
   calibrated measurement
       = raw measurement - calculated no-message baseline
       = {message.measured:.6f} - {expected_baseline:.6f}
       = {message.observed_delta:.6f}
   decoded m = observed displacement / response factor
             = {message.observed_delta:.6f} / {message.response_factor:.6f}
             = {message.decoded_value:.6f}
   random residual = {random_residual:.6f}
   decoded random error = {decoded_random_error:.6f}

sent bits = {message.sent_bits}
decoded bits = {message.decoded_bits}
protocol accepted = {result.accepted}
"""
    )


if __name__ == "__main__":
    main()
