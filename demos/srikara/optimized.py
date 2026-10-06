"""Send a message with the fully optimized Srikara settings and print a compact summary.

The settings are the benchmark's last optimization step: aligned measurement,
Gray-labelled intervals, r = 0.576 (5 dB), theta = 3pi/2, a parity bit per symbol and up
to 3 sends per block. One line per block, then a short look inside one block.

Examples:
    python demos/srikara/optimized.py "hello world"
    python demos/srikara/optimized.py "hello world" --noise metro_10km --example 2
"""

from __future__ import annotations

import argparse

from walkthrough import header, table

from qsdc.common.bits import bits_to_bytes, bytes_to_bits, hamming_distance
from qsdc.protocols.srikara.benchmark.catalog import NOISES, SIMULATORS
from qsdc.protocols.srikara.config import Fixed
from qsdc.protocols.srikara.simulator.protocol import (
    Attempt,
    SrikaraSimulator,
    Transmission,
)
from qsdc.protocols.srikara.simulator.transport import odd_parity

RETRY = SIMULATORS["retry"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "message", nargs="?", help="text to send; prompted for if omitted"
    )
    parser.add_argument("--noise", choices=list(NOISES), default="lab")
    parser.add_argument("--squeeze-r", type=float, default=RETRY.squeeze_r.value)
    parser.add_argument("--seed", type=int, default=RETRY.seed)
    parser.add_argument(
        "--example",
        type=int,
        help="block to look inside (default: the most eventful one)",
    )
    args = parser.parse_args()

    message = args.message if args.message is not None else input("Message: ")
    config = RETRY.model_copy(
        update={
            "noise": NOISES[args.noise],
            "squeeze_r": Fixed(value=args.squeeze_r),
            "seed": args.seed,
        }
    )
    payload = bytes_to_bits(message.encode())
    transmission = SrikaraSimulator(config).transmit(payload)
    blocks = group_by_block(transmission)

    header("Optimized Srikara transfer")
    print(
        f"{config.backend}, noise '{args.noise}', r = {args.squeeze_r:g}, theta = {config.theta_pi}pi, "
        f"{config.intervals} intervals, {config.axis_policy} axis,\n"
        f"parity, all checks must pass, up to {config.max_attempts} sends per block"
    )
    states = len(transmission.attempts[0].run.states)
    print(
        f"\n{message!r} -> {len(payload)} bits -> {len(blocks)} blocks of 2 bits "
        f"(+1 parity bit), {states} states per send"
    )

    header("Blocks")
    table(
        ("Block", "Bits", "Send", "Failed checks", "Wrong symbols", "Parity", "Result"),
        [
            row
            for number, sends in enumerate(blocks)
            for row in block_rows(number, sends)
        ],
    )

    number = args.example if args.example is not None else most_eventful(blocks)
    show_example(number, blocks[number])
    show_result(message, payload, transmission)


def group_by_block(transmission: Transmission) -> list[list[Attempt]]:
    blocks: dict[int, list[Attempt]] = {}
    for attempt in transmission.attempts:
        blocks.setdefault(attempt.block.offset, []).append(attempt)
    return list(blocks.values())


def block_rows(number: int, sends: list[Attempt]) -> list[tuple[object, ...]]:
    block = sends[0].block
    rows = []
    for attempt in sends:
        run = attempt.run
        checks = run.controls + run.decoys
        failed = sum(not check.passed for check in checks)
        wrong = sum(m.decoded_bits != m.sent_bits for m in run.messages)
        rows.append(
            (
                number if attempt.number == 0 else "",
                f"{block.offset}-{block.offset + len(block.bits) - 1}"
                if attempt.number == 0
                else "",
                attempt.number + 1,
                f"{failed}/{len(checks)}",
                f"{wrong}/{len(run.messages)}",
                parity_summary(attempt),
                outcome(attempt),
            )
        )
    return rows


def parity_summary(attempt: Attempt) -> str:
    if not attempt.run.accepted:
        return "-"
    return "ok" if attempt.decoded_bits is not None else "error detected"


def outcome(attempt: Attempt) -> str:
    if not attempt.run.accepted:
        return "rejected, send again"
    if attempt.decoded_bits is None:
        return "withheld, send again"
    errors = hamming_distance(attempt.decoded_bits, attempt.block.bits)
    return "released" if not errors else f"released, {errors} wrong bit(s)"


def most_eventful(blocks: list[list[Attempt]]) -> int:
    """The block with the most sends, then the most corrected symbols."""

    def score(sends: list[Attempt]) -> tuple[int, int]:
        last = sends[-1].run.messages
        return len(sends), sum(m.decoded_bits != m.sent_bits for m in last)

    return max(range(len(blocks)), key=lambda number: score(blocks[number]))


def show_example(number: int, sends: list[Attempt]) -> None:
    block = sends[0].block
    header(f"Inside block {number}")
    print(f"Payload bits {block.bits}, sent as symbols {' '.join(block.symbols)}")
    for attempt in sends:
        run = attempt.run
        checks = run.controls + run.decoys
        worst = max(abs(c.measured - c.expected) / c.sigma for c in checks)
        print(
            f"\nSend {attempt.number + 1}: {len(run.controls)} control and {len(run.decoys)} "
            f"decoy checks, {sum(not c.passed for c in checks)} failed, "
            f"worst deviation {worst:.2f} sigma -> {'accepted' if run.accepted else 'rejected'}"
        )
        received = [m.decoded_bits for m in run.messages]
        marks = " ".join(
            bits if bits == m.sent_bits else f"[{bits}]"
            for bits, m in zip(received, run.messages)
        )
        print(f"  received symbols: {marks}   ([..] = decoded wrong)")
        wrong = next(
            (m for m in run.messages if m.decoded_bits != m.sent_bits), run.messages[0]
        )
        print(
            f"  e.g. mode {wrong.index}: Alice sent {wrong.sent_bits} as m = {wrong.value:+.3f}; "
            f"Bob read {wrong.axis.name} = {wrong.measured:+.3f}, baseline {wrong.baseline:+.3f}, "
            f"response {wrong.response:+.3f} -> m = {wrong.decoded_value:+.3f} -> {wrong.decoded_bits}"
        )
        if run.accepted:
            word, odd = received[0], odd_parity(block.offset)
            ones = word.count("1")
            passed = ones % 2 == odd
            verdict = "passes" if passed else "error detected, block withheld"
            print(
                f"  {'odd' if odd else 'even'} parity of {word}: {ones} ones, {verdict}"
            )
        print(f"  -> {outcome(attempt)}")


def show_result(message: str, payload: str, transmission: Transmission) -> None:
    attempts = transmission.attempts
    blocks = transmission.final_attempts
    messages = [m for attempt in attempts for m in attempt.run.messages]
    header("Result")
    retries = len(attempts) - len(blocks)
    print(
        f"Sends: {len(attempts)} for {len(blocks)} blocks ({retries} {'retry' if retries == 1 else 'retries'})"
    )
    print(f"States prepared: {sum(len(a.run.states) for a in attempts)}")
    raw = sum(hamming_distance(m.sent_bits, m.decoded_bits) for m in messages)
    print(f"Bit errors before correction: {raw} / {3 * len(messages)}")
    recovered = transmission.recovered_bits
    if recovered is None:
        missing = sum(a.decoded_bits is None for a in blocks)
        print(f"No message released: {missing} block(s) failed every send.")
        return
    errors = hamming_distance(recovered, payload)
    text = bits_to_bytes(recovered).decode(errors="replace")
    print(f"Bit errors after correction: {errors} / {len(payload)}")
    print(f"Recovered: {text!r} ({'exact' if text == message else 'corrupted'})")


if __name__ == "__main__":
    main()
