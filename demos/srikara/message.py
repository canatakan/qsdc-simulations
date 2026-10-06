"""Send a text message through the simulated Srikara CV-QSDC channel and print every step.

On the Strawberry Fields backends every measured mode is also traced through the optical
stages (preparation, channels, memory, Alice's displacement, unsqueezing, detection).

Examples:
    python demos/srikara/message.py "hello"
    python demos/srikara/message.py "hi" --backend analytic
    python demos/srikara/message.py "hello" --optimized --noise medium --error-correction secded --max-attempts 3
"""

from __future__ import annotations

import argparse

from walkthrough import show_transmission

from qsdc.common.bits import bytes_to_bits
from qsdc.protocols.srikara.benchmark.catalog import NOISES, OPTIMIZED
from qsdc.protocols.srikara.config import SimulatorConfig
from qsdc.protocols.srikara.simulator.protocol import SrikaraSimulator


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "message", nargs="?", help="text to send; prompted for if omitted"
    )
    parser.add_argument(
        "--backend", choices=("analytic", "sf", "sf-sampled"), default="sf-sampled"
    )
    parser.add_argument(
        "--random-source", choices=("classical", "sf-bs-qrng"), default="classical"
    )
    parser.add_argument("--seed", type=int, default=SimulatorConfig().seed)
    parser.add_argument(
        "--noise",
        choices=list(NOISES),
        default="clean",
        help="noise preset (sf backends only)",
    )
    parser.add_argument("--tolerance-sigmas", type=float, default=3.0)
    parser.add_argument(
        "--optimized",
        action="store_true",
        help="the benchmark's optimized settings: aligned measurement, Gray-labelled "
        "intervals, "
        "r = 0.576 (5 dB) and theta = 3pi/2",
    )
    parser.add_argument(
        "--error-correction",
        choices=("none", "parity", "secded"),
        default="none",
        help="parity: 2 payload bits + 1 parity bit per symbol; secded: interleaved SECDED",
    )
    parser.add_argument(
        "--max-attempts", type=int, default=1, help="attempts per block"
    )
    parser.add_argument(
        "--no-trace", action="store_true", help="skip the per-mode optical noise traces"
    )
    args = parser.parse_args()

    message = args.message if args.message is not None else input("Message: ")
    config = SimulatorConfig(
        backend=args.backend,
        random_source=args.random_source,
        seed=args.seed,
        noise=NOISES[args.noise],
        tolerance_sigmas=args.tolerance_sigmas,
        error_correction=args.error_correction,
        max_attempts=args.max_attempts,
    )
    if args.optimized:
        config = config.model_copy(
            update={
                "axis_policy": OPTIMIZED.axis_policy,
                "intervals": OPTIMIZED.intervals,
                "squeeze_r": OPTIMIZED.squeeze_r,
                "theta_pi": OPTIMIZED.theta_pi,
            }
        )
    payload = bytes_to_bits(message.encode())
    transmission = SrikaraSimulator(config).transmit(payload)
    trace = config.backend != "analytic" and not args.no_trace
    show_transmission(config, message, payload, transmission, trace)


if __name__ == "__main__":
    main()
