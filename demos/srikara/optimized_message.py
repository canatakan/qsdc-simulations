"""Send one text message with the optimized Srikara settings.

Examples:
    python demos/srikara/optimized_message.py "hello"
    python demos/srikara/optimized_message.py "hello" --noise --secded --max-attempts 3
"""

from __future__ import annotations

import argparse

from qsdc.common.bits import bits_to_bytes, bytes_to_bits
from qsdc.protocols.srikara.configuration.distribution import FixedSqueezeConfig
from qsdc.protocols.srikara.configuration.noise import (
    ElectronicNoiseConfig,
    NoiseConfig,
    ThermalLossConfig,
)
from qsdc.protocols.srikara.configuration.simulator import SimulatorConfig
from qsdc.protocols.srikara.simulator.protocol import simulate_qsdc

MIDDLE_SQUEEZING = 0.864
CHECK_TOLERANCE_SIGMAS = 3.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("message", nargs="?", help="text to send")
    parser.add_argument("--encoding", default="utf-8")
    parser.add_argument("--seed", type=int, default=20260821)
    parser.add_argument(
        "--noise",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="use the thermal-loss and electronic-readout noise model",
    )
    parser.add_argument(
        "--secded",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="protect the logical payload with interleaved Hamming SECDED",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=1,
        help="per-block attempt limit when --secded is enabled (default: 1)",
    )
    args = parser.parse_args()

    if args.max_attempts < 1:
        parser.error("--max-attempts must be at least 1")
    if args.max_attempts > 1 and not args.secded:
        parser.error("--max-attempts > 1 requires --secded")

    message = args.message if args.message is not None else input("Message: ")
    if not message:
        parser.error("message must not be empty")

    payload = message.encode(args.encoding)
    payload_bits = bytes_to_bits(payload)
    noise = _demo_noise() if args.noise else NoiseConfig()
    config = SimulatorConfig(
        backend="sf-noise" if args.noise else "analytic",
        noise=noise,
        seed=args.seed,
        intervals="optimized_v12",
        tolerance_sigmas=CHECK_TOLERANCE_SIGMAS,
        check_axis_policy="optimized",
        message_axis_policy="optimized",
        squeeze_r_distribution=FixedSqueezeConfig(value=MIDDLE_SQUEEZING),
        error_correction="secded" if args.secded else "none",
        max_attempts_per_block=args.max_attempts,
    )
    result = simulate_qsdc(payload_bits, config)

    print("Optimized Srikara message demo")
    print(f"Input: {message!r}")
    print(f"Payload: {len(payload)} bytes / {len(payload_bits)} bits")
    print(
        "Settings: "
        f"intervals=optimized_v12, axes=optimized, "
        f"tolerance={CHECK_TOLERANCE_SIGMAS:g}σ, "
        f"r={MIDDLE_SQUEEZING:g}, noise={'on' if args.noise else 'off'}, "
        f"secded={'on' if args.secded else 'off'}"
    )
    print(
        f"Transport blocks: {len(result.blocks)}; "
        f"attempts: {result.total_attempt_count}"
    )
    print(f"Delivery status: {result.delivery_status}")

    recovered_bits = result.recovered_bits
    if recovered_bits is None:
        print(
            "No payload released. Blocks needing another attempt: "
            f"{result.exhausted_blocks}"
        )
        return

    recovered = bits_to_bytes(recovered_bits).decode(args.encoding, errors="replace")
    print(f"Recovered: {recovered!r}")
    print(f"Exact match: {recovered == message}")


def _demo_noise() -> NoiseConfig:
    """Use the same modest noise profile as the temporary comparisons."""

    loss = ThermalLossConfig(transmittance=0.95, environment_nbar=0.01)
    readout = ElectronicNoiseConfig(variance_snu=0.002)
    return NoiseConfig(
        forward=[loss],
        return_path=[loss],
        alice_readout=[readout],
        bob_readout=[readout],
    )


if __name__ == "__main__":
    main()
