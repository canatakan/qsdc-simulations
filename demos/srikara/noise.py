"""Send a short message through a noisy channel and follow every mode through every noise stage.

Examples:
    python demos/srikara/noise.py
    python demos/srikara/noise.py "Hi" --error-correction parity --max-attempts 2
"""

from __future__ import annotations

import argparse

from walkthrough import header, show_transmission, table

from qsdc.common.bits import bytes_to_bits
from qsdc.protocols.srikara.config import (
    Channel,
    Detector,
    Memory,
    NoiseConfig,
    SimulatorConfig,
    Uniform,
)
from qsdc.protocols.srikara.simulator.backends import VACUUM_VARIANCE
from qsdc.protocols.srikara.simulator.protocol import SrikaraSimulator

NOISE = NoiseConfig(
    forward=Channel(transmittance=0.9),
    memory=Memory(seconds=0.5, lifetime_seconds=2.0, efficiency=0.9, nbar=0.01),
    backward=Channel(transmittance=0.9, nbar=0.02),
    alice_detector=Detector(efficiency=0.95, electronic_variance=0.02),
    bob_detector=Detector(efficiency=0.95, electronic_variance=0.02),
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "message", nargs="?", default="Q", help="text to send (default: Q)"
    )
    parser.add_argument("--seed", type=int, default=4)
    parser.add_argument(
        "--error-correction",
        choices=("none", "parity", "secded"),
        default="none",
        help="parity: 2 payload bits + 1 parity bit per symbol; secded: interleaved SECDED",
    )
    parser.add_argument(
        "--max-attempts", type=int, default=1, help="attempts per block"
    )
    args = parser.parse_args()

    config = SimulatorConfig(
        backend="sf-sampled",
        noise=NOISE,
        intervals="gaussian_gray",
        squeeze_r=Uniform(lower=0.25, upper=1.0),
        tolerance_sigmas=4.0,
        axis_policy="best_qp",
        seed=args.seed,
        error_correction=args.error_correction,
        max_attempts=args.max_attempts,
    )
    explain_noise()
    payload = bytes_to_bits(args.message.encode())
    transmission = SrikaraSimulator(config).transmit(payload)
    show_transmission(config, args.message, payload, transmission, trace_noise=True)


def explain_noise() -> None:
    header("How each noise stage acts on one quadrature (mean mu, variance V)")
    v0 = VACUUM_VARIANCE
    memory = NOISE.memory
    table(
        ("Stage", "Mean", "Variance"),
        [
            (
                "Thermal loss (T, nbar)",
                "mu -> sqrt(T) mu",
                f"V -> T V + (1 - T)(2 nbar + 1) {v0}",
            ),
            (
                "Pure loss / detector (eta)",
                "mu -> sqrt(eta) mu",
                f"V -> eta V + (1 - eta) {v0}",
            ),
            (
                "Memory",
                "thermal loss with",
                f"T = eff exp(-t / lifetime) = {memory.transmittance:.4f}",
            ),
            ("Electronic readout (v SNU)", "unchanged", f"V -> V + v * {v0}"),
            (
                "Squeezing S(s), unsqueezing S(-s)",
                "linear map",
                "stretches one axis, shrinks the other",
            ),
        ],
    )
    print(
        "\nAlice's displacement happens after the channel to Alice and the memory, so only the\n"
        "channel back to Bob and Bob's detector attenuate the message: response gain\n"
        f"sqrt(T_back * eta_Bob) = {(NOISE.backward.transmittance * NOISE.bob_detector.efficiency) ** 0.5:.4f}.\n"
        "Checks use the expected mean and variance of this noisy channel, so honest noise\n"
        "widens the tolerance instead of failing the checks."
    )


if __name__ == "__main__":
    main()
