"""Send a text message through the simulated CV QSDC channel."""

from __future__ import annotations

import argparse
import textwrap

from qsdc.common.bits import bits_to_bytes, bytes_to_bits
from qsdc.protocols.srikara.configuration.simulator import SimulatorConfig
from qsdc.protocols.srikara.simulator.encoding import (
    ENCODING_INTERVALS,
    interval_for_bits,
)
from qsdc.protocols.srikara.simulator.protocol import simulate_qsdc


def main() -> None:
    defaults = SimulatorConfig()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "message",
        nargs="?",
        help="text message to transmit; if omitted, the script prompts for it",
    )
    parser.add_argument(
        "--backend",
        choices=("analytic", "sf", "sf-sampled", "sf-noise"),
        default="sf-sampled",
        help="simulation backend",
    )
    parser.add_argument("--seed", type=int, default=defaults.seed)
    parser.add_argument("--encoding", default="utf-8")
    parser.add_argument(
        "--tolerance-sigmas",
        type=float,
        default=None,
        help="control/decoy measurement-noise-sigma tolerance",
    )
    parser.add_argument(
        "--random-source",
        choices=("classical", "sf-bs-qrng"),
        default="classical",
        help="protocol random source for routing, basis choices, and values",
    )
    parser.add_argument(
        "--intervals",
        choices=tuple(ENCODING_INTERVALS),
        default=defaults.intervals,
        help="message interval strategy",
    )
    parser.add_argument(
        "--message-axis-policy",
        choices=("random", "optimized"),
        default=defaults.message_axis_policy,
        help=(
            "message decoding axis policy; optimized chooses the q/p axis "
            "with the larger absolute response factor"
        ),
    )
    args = parser.parse_args()

    message = args.message if args.message is not None else input("Message: ")
    if message == "":
        raise ValueError("empty messages are not useful for this demo")

    payload = message.encode(args.encoding)
    bitstream = bytes_to_bits(payload)
    padding = (-len(bitstream)) % 3
    padded_bitstream = bitstream + ("0" * padding)
    symbols = tuple(
        padded_bitstream[index : index + 3]
        for index in range(0, len(padded_bitstream), 3)
    )

    config_overrides = {
        "backend": args.backend,
        "random_source": args.random_source,
        "seed": args.seed,
        "intervals": args.intervals,
        "message_axis_policy": args.message_axis_policy,
    }
    if args.tolerance_sigmas is not None:
        config_overrides["tolerance_sigmas"] = args.tolerance_sigmas
    config = SimulatorConfig.model_validate(config_overrides)
    result = simulate_qsdc(bitstream, config)
    protocol = result.blocks[0].protocol

    decoded_symbols = tuple(
        message_mode.decoded_bits for message_mode in protocol.messages
    )
    decoded_bitstream = "".join(decoded_symbols)
    unpadded_bits = decoded_bitstream[:-padding] if padding else decoded_bitstream
    decoded_payload = bits_to_bytes(unpadded_bits)
    decoded_message = decoded_payload.decode(args.encoding, errors="replace")

    print_header("1. User message")
    print(f"Input text: {message!r}")
    print(f"Text encoding: {args.encoding}")
    print(f"Payload bytes ({len(payload)}): {payload.hex(' ')}")

    print_header("2. Classical bit representation")
    print(f"Raw bitstream ({len(bitstream)} bits):")
    print_wrapped(bitstream)
    print(f"Padding added for 3-bit QSDC symbols: {padding} zero bit(s)")
    print(f"Padded bitstream ({len(padded_bitstream)} bits):")
    print_wrapped(padded_bitstream)
    print("3-bit symbols that will be sent by Alice:")
    print_symbol_rows(symbols)

    print_header("3. Quantum channel configuration")
    print(f"Backend: {protocol.backend_name}")
    print(f"Protocol random source: {protocol.random_source_name}")
    print(f"Intervals: {protocol.intervals}")
    print(f"Message axis policy: {protocol.message_axis_policy}")
    print(f"Random seed: {args.seed}")
    print(f"Backend measurement seed: {args.seed}")
    print(
        "Control/decoy tolerance "
        f"(measurement noise sigmas): {protocol.check_tolerance_sigmas:g}"
    )
    print(f"Nominal shot-noise sigma: {protocol.measurement_noise_sigma:g}")

    print()

    print(f"Total optical modes n: {len(protocol.prepared_states)}")
    print(f"Control modes n/2: {len(protocol.control_indices)}")
    print(f"Message modes n/4: {len(protocol.message_indices)}")
    print(f"Decoy modes n/4: {len(protocol.decoy_indices)}")
    print(f"Delayed modes n/2: {len(protocol.route.delayed_indices)}")

    print()

    print(f"Control coordinates: {protocol.control_indices}")
    print(f"Delayed coordinates: {protocol.route.delayed_indices}")
    print(f"Message coordinates: {protocol.message_indices}")
    print(f"Decoy coordinates: {protocol.decoy_indices}")

    print_header("4. Bob prepares S(s_j)D(alpha_j)|0>")
    print("idx  alpha_j                         r_j        theta_j")
    for state in protocol.prepared_states:
        print(
            f"{state.index:>3}  {format_complex(state.alpha):<30} "
            f"{state.squeeze_r:>8.5f}  {state.theta:>9.5f}"
        )

    print()
    print(
        "Announcement via classical channel (Alice -> Bob): "
        f"{protocol.transcript.control_coordinates.label}"
    )

    print_header("5. Alice checks control modes")
    print(
        "Announcement via classical channel (Bob -> Alice): "
        f"{protocol.transcript.control_parameter_coordinates.label}"
    )
    print()

    print("idx  axis  expected       measured       sigma       dev/sigma   status")
    for check in protocol.controls:
        status = "pass" if check.passed else "fail"
        sigma_deviation = abs(check.measured - check.expected) / check.expected_sigma
        print(
            f"{check.index:>3}  {check.axis:>4}  "
            f"{check.expected:>12.7f}  {check.measured:>12.7f}  "
            f"{check.expected_sigma:>10.7f}  {sigma_deviation:>9.4f}  {status}"
        )
    print(f"Control check result: {protocol.control_passed}")

    print_header("6. Alice encodes message modes with D(beta_A)")
    print("idx  bits  interval       m_A           beta_A")
    for message_mode in protocol.messages:
        interval = interval_for_bits(
            message_mode.sent_bits,
            intervals=message_mode.intervals,
        )
        print(
            f"{message_mode.index:>3}  {message_mode.sent_bits:>4}  "
            f"{format_interval(interval.lower, interval.upper):<13} "
            f"{message_mode.message_value:>11.7f}  "
            f"{format_complex(message_mode.alice_beta)}"
        )

    print_header("7. Bob checks returned decoys")
    print(
        "Announcement via classical channel (Alice -> Bob): "
        f"{protocol.transcript.decoy_coordinates.label}"
    )
    print()

    print("idx  axis  expected       measured       sigma       dev/sigma   status")
    for decoy in protocol.decoys:
        status = "pass" if decoy.passed else "fail"
        sigma_deviation = abs(decoy.measured - decoy.expected) / decoy.expected_sigma
        print(
            f"{decoy.index:>3}  {decoy.axis:>4}  "
            f"{decoy.expected:>12.7f}  {decoy.measured:>12.7f}  "
            f"{decoy.expected_sigma:>10.7f}  {sigma_deviation:>9.4f}  {status}"
        )
    print(f"Decoy check result: {protocol.decoy_passed}")

    print_header("8. Bob decodes message modes")
    print(
        "idx  axis  sent  decoded  measured      Delta        factor       m recovered"
    )
    for message_mode in protocol.messages:
        print(
            f"{message_mode.index:>3}  {message_mode.axis:>4}  "
            f"{message_mode.sent_bits:>4}  "
            f"{message_mode.decoded_bits:>7}  "
            f"{message_mode.measured:>11.7f}  "
            f"{message_mode.observed_delta:>11.7f}  "
            f"{message_mode.response_factor:>11.7f}  "
            f"{message_mode.decoded_value:>11.7f}"
        )

    print_header("9. Reconstructed classical message")
    print(f"Decoded 3-bit symbols: {' '.join(decoded_symbols)}")
    print(f"Decoded padded bitstream ({len(decoded_bitstream)} bits):")
    print_wrapped(decoded_bitstream)
    if padding:
        print(f"Removed {padding} padding bit(s).")
    print(f"Recovered payload bytes: {decoded_payload.hex(' ')}")
    print(f"Recovered text: {decoded_message!r}")
    print(f"Protocol accepted: {result.accepted}")


def print_header(title: str) -> None:
    print()
    print("=" * len(title))
    print(title)
    print("=" * len(title))


def print_wrapped(bits: str, width: int = 72) -> None:
    for line in textwrap.wrap(bits, width=width):
        print(line)


def print_symbol_rows(symbols: tuple[str, ...], per_row: int = 16) -> None:
    for index in range(0, len(symbols), per_row):
        row = symbols[index : index + per_row]
        print(f"{index:>3}-{index + len(row) - 1:<3}: {' '.join(row)}")


def format_complex(value: complex) -> str:
    sign = "+" if value.imag >= 0 else "-"
    return f"{value.real: .7f} {sign} {abs(value.imag):.7f}i"


def format_interval(lower: float, upper: float) -> str:
    left = "-inf" if lower == float("-inf") else f"{lower:g}"
    right = "inf" if upper == float("inf") else f"{upper:g}"
    return f"({left}, {right})"


if __name__ == "__main__":
    main()
