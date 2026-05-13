"""Send a text message through the simulated CV QSDC channel."""

from __future__ import annotations

import argparse
import textwrap

from simulator.backends import make_backend
from simulator.core.config import ProtocolConfig
from simulator.core.encoding import interval_for_bits
from simulator.core.protocol import simulate_qsdc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "message",
        nargs="?",
        help="text message to transmit; if omitted, the script prompts for it",
    )
    parser.add_argument(
        "--backend",
        choices=(
            "analytic",
            "sf",
            "sf-sampled",
        ),
        default="sf",
        help="simulation backend",
    )
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--encoding", default="utf-8")
    parser.add_argument(
        "--tolerance",
        type=float,
        default=None,
        help="override control/decoy tolerance; defaults to the backend value",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="number of repeated homodyne samples to average for sf-sampled",
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

    config = ProtocolConfig(
        n_states=4 * len(symbols),
        seed=args.seed,
        tolerance=args.tolerance,
    )
    result = simulate_qsdc(
        symbols,
        config=config,
        backend=make_backend(args.backend, sampled_repetitions=args.repetitions),
    )

    decoded_symbols = tuple(message_mode.decoded_bits for message_mode in result.messages)
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
    print("3-bit symbols selected for transmission:")
    print_symbol_rows(symbols)

    print_header("3. Quantum channel configuration")
    print(f"Backend: {result.backend_name}")
    print(f"Random seed: {args.seed}")
    if result.backend_name == "sf-sampled":
        print(f"Sample repetitions: {args.repetitions}")
    print(f"Control/decoy tolerance: {result.check_tolerance:g}")
    print(f"Total optical modes n: {config.n_states}")
    print(f"Control modes n/2: {len(result.control_indices)}")
    print(f"Message modes n/4: {len(result.message_indices)}")
    print(f"Decoy modes n/4: {len(result.decoy_indices)}")
    print(f"Control coordinates: {result.control_indices}")
    print(f"Message coordinates: {result.message_indices}")
    print(f"Decoy coordinates: {result.decoy_indices}")

    print_header("4. State preparation S(s_j)D(alpha_j)|0>")
    print("idx  alpha_j                         r_j        theta_j")
    for state in result.prepared_states:
        print(
            f"{state.index:>3}  {format_complex(state.alpha):<30} "
            f"{state.squeeze_r:>8.5f}  {state.theta:>9.5f}"
        )

    print_header("5. Control-mode checks")
    print("idx  axis  expected       measured       status")
    for check in result.controls:
        status = "pass" if check.passed else "fail"
        print(
            f"{check.index:>3}  {check.axis:>4}  "
            f"{check.expected:>12.7f}  {check.measured:>12.7f}  {status}"
        )
    print(f"Control check result: {result.control_passed}")

    print_header("6. Message-mode encoding with D(beta_m)")
    print("idx  bits  interval       m             beta_m")
    for message_mode in result.messages:
        interval = interval_for_bits(message_mode.sent_bits)
        print(
            f"{message_mode.index:>3}  {message_mode.sent_bits:>4}  "
            f"{format_interval(interval.lower, interval.upper):<13} "
            f"{message_mode.message_value:>11.7f}  "
            f"{format_complex(message_mode.message_beta)}"
        )

    print_header("7. Returned decoy checks")
    print("idx  axis  expected       measured       status")
    for decoy in result.decoys:
        status = "pass" if decoy.passed else "fail"
        print(
            f"{decoy.index:>3}  {decoy.axis:>4}  "
            f"{decoy.expected:>12.7f}  {decoy.measured:>12.7f}  {status}"
        )
    print(f"Decoy check result: {result.decoy_passed}")

    print_header("8. Message-mode decoding")
    print("idx  axis  sent  decoded  measured      Delta        factor       m recovered")
    for message_mode in result.messages:
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


def bytes_to_bits(payload: bytes) -> str:
    return "".join(f"{byte:08b}" for byte in payload)


def bits_to_bytes(bits: str) -> bytes:
    if len(bits) % 8 != 0:
        raise ValueError("decoded bitstream length is not byte-aligned")
    return bytes(int(bits[index : index + 8], 2) for index in range(0, len(bits), 8))


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
