"""Send a text message through the simulated Cao et al. CV-QSDC protocol.

Prints the settings, one line per send, every protocol step of one block and the
recovered message. --noise picks a noise baseline; the default, clean, leaves
only the vacuum noise of the squeezed states and of the measurements.

Examples:
    cao-demo "hello"
    cao-demo "hello" --max-attempts 3 --block 2
    cao-demo "hello" --noise metro_10km --squeeze-r 3
"""

from __future__ import annotations

import argparse
from math import e, log10, sqrt

from qsdc.common.coding.bits import bits_to_bytes, bytes_to_bits, hamming_distance
from qsdc.common.utils import header, interval, step, table
from qsdc.protocols.cao.config import NOISES, SimulatorConfig
from qsdc.protocols.cao.constants import EPR_BOUND
from qsdc.protocols.cao.simulator.mapping import interval_code, restore_block
from qsdc.protocols.cao.simulator.protocol import (
    Attempt,
    Simulator,
    Stage,
    Transmission,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cao-demo",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("message", nargs="?", default="hello")
    parser.add_argument("--noise", choices=list(NOISES), default="clean")
    parser.add_argument("--random-source", choices=("classical", "sf-bs-qrng"))
    parser.add_argument("--seed", type=int)
    parser.add_argument("--squeeze-r", type=float)
    parser.add_argument("--check-pairs", type=int, help="pairs per check stage")
    parser.add_argument("--max-attempts", type=int, help="sends per block")
    parser.add_argument(
        "--block", type=int, help="block to show in detail (default: most sends)"
    )
    args = parser.parse_args()

    fields = ("random_source", "seed", "squeeze_r", "check_pairs", "max_attempts")
    update = {f: getattr(args, f) for f in fields if getattr(args, f) is not None}
    config = SimulatorConfig(noise=NOISES[args.noise], **update)
    payload = bytes_to_bits(args.message.encode())
    transmission = Simulator(config).transmit(payload)
    blocks = group_by_block(transmission)

    show_settings(config, args.noise)
    print(
        f"\n{args.message!r} -> {len(payload)} bits -> {len(blocks)} blocks, "
        f"{transmission.attempts[0].run.pairs} EPR pairs per send"
    )
    show_sends(blocks)
    number = args.block if args.block is not None else most_eventful(blocks)
    for attempt in blocks[number]:
        show_attempt(attempt, number, config)
    show_result(args.message, payload, transmission)


def group_by_block(transmission: Transmission) -> list[list[Attempt]]:
    blocks: dict[int, list[Attempt]] = {}
    for attempt in transmission.attempts:
        blocks.setdefault(attempt.block.offset, []).append(attempt)
    return list(blocks.values())


def most_eventful(blocks: list[list[Attempt]]) -> int:
    def score(sends: list[Attempt]) -> tuple[int, int]:
        signals = sends[-1].run.signals
        return len(sends), sum(s.decoded_bits != s.box.bits for s in signals)

    return max(range(len(blocks)), key=lambda number: score(blocks[number]))


def show_settings(config: SimulatorConfig, noise: str) -> None:
    header(f"Cao et al., noise '{noise}'")
    width = config.box_bits + config.detection_bits
    table(
        ("Setting", "Value"),
        [
            ("Random source", f"{config.random_source} (seed {config.seed})"),
            (
                "Squeezing r",
                f"{config.squeeze_r:.4f} ({20 * config.squeeze_r * log10(e):.1f} dB)",
            ),
            ("Modulation variance V_A", f"{config.modulation_variance_snu:g} SNU"),
            ("Message bits per block", config.block_bits),
            ("Boxes per block", config.boxes),
            ("Payload bits per box", config.box_bits),
            ("Detection bits per box", config.detection_bits),
            ("Gaussian intervals", f"{2**width} ({width} bits)"),
            ("Check pairs per stage", config.check_pairs),
            ("Check failure threshold", f"{config.check_failure_threshold:.4f}"),
            ("Sends per block", f"at most {config.max_attempts}"),
        ],
    )
    n = config.noise
    print(
        f"\nFibre T = {n.channel.transmittance:g} (nbar {n.channel.nbar:g}), "
        f"delay lines T = {n.alice_memory.transmittance:.4g} / {n.bob_memory.transmittance:.4g}, "
        f"detector eta = {n.bob_detector.efficiency:g}, v_el = {n.bob_detector.electronic_variance:g} SNU"
    )


def show_sends(blocks: list[list[Attempt]]) -> None:
    header("Sends")
    rows = []
    for number, sends in enumerate(blocks):
        block = sends[0].block
        for attempt in sends:
            run = attempt.run
            first = attempt.number == 0
            rows.append(
                (
                    number if first else "",
                    block.bits if first else "",
                    attempt.number + 1,
                    failures(run.channel),
                    failures(run.authentication) if run.authentication else "",
                    " ".join(s.box.bits for s in run.signals),
                    " ".join(s.decoded_bits for s in run.signals),
                    outcome(attempt),
                )
            )
    table(
        ("Block", "Bits", "Send", "Channel", "Auth", "Mapped", "Decoded", "Result"),
        rows,
    )


def failures(stage: Stage) -> str:
    return f"{sum(not c.passed for c in stage.checks)}/{len(stage.checks)}"


def outcome(attempt: Attempt) -> str:
    if not attempt.run.accepted:
        return "terminated"
    if attempt.decoded_bits is None:
        return "error detected, withheld"
    errors = hamming_distance(attempt.decoded_bits, attempt.block.bits)
    return "released" if not errors else f"released, {errors} wrong bit(s)"


def show_attempt(attempt: Attempt, number: int, config: SimulatorConfig) -> None:
    run, block = attempt.run, attempt.block
    code = interval_code(config)
    header(f"Block {number}, send {attempt.number + 1}")

    step("1. Alice prepares EPR pairs (Eqs. 1-4) and sends S2 of each to Bob")
    print(
        f"{run.pairs} pairs: {2 * config.check_pairs} for the checks, "
        f"{config.boxes} for the boxes"
    )

    step("2. Channel detection: both heterodyne the positions Alice picks (Eq. 5)")
    show_stage(run.channel)
    if run.authentication is not None:
        step("3. Authentication: the same test on positions Bob picks")
        show_stage(run.authentication)
    if not run.accepted:
        print("-> communication terminated")
        return

    step("4. Gaussian mapping")
    block_uniformized = "".join(s.box.payload for s in run.signals)
    print(f"Message bits            {block.bits}")
    print(f"Message uniformization  {block.uniformized}")
    print(f"Block uniformization    {block_uniformized}")
    table(
        ("Box", "Payload", "Detection at", "Mapped", "Parity", "Interval"),
        [
            (
                i,
                s.box.payload,
                ", ".join(str(position) for position in s.box.detection),
                s.box.bits,
                s.box.parity,
                interval(*code.interval(s.box.bits)),
            )
            for i, s in enumerate(run.signals)
        ],
    )

    step("5. Alice displaces X of S1 by G1' and P by G2, sends S_info to Bob")
    table(
        ("j", "Mapped", "G1'", "G2"),
        [(s.index, s.box.bits, f"{s.g1:+.4f}", f"{s.g2:+.4f}") for s in run.signals],
    )

    step("6. Bob measures S_info jointly with S2 (Eq. 6)")
    table(
        ("j", "X_m", "P_m"),
        [
            (s.index, f"{s.measured.real:+.4f}", f"{s.measured.imag:+.4f}")
            for s in run.signals
        ],
    )

    step("7. Alice reveals G2, Bob estimates his gain and inverts the mapping")
    n = config.noise
    expected = sqrt(n.bob_detector.efficiency * n.channel.transmittance / 2)
    print(f"Gain from P_m = t G2: t = {run.gain:.4f} (expected: {expected:.4f})")
    table(
        ("j", "X_m / t", "Decoded", "Mapped", "Detection", "Parity", "Payload"),
        [
            (
                s.index,
                f"{s.decoded_value:+.4f}",
                s.decoded_bits,
                s.box.bits,
                "ok" if s.detection_valid else "WRONG",
                "ok" if s.parity_valid else "FAIL",
                s.decoded_payload,
            )
            for s in run.signals
        ],
    )
    if attempt.decoded_bits is not None:
        payload = "".join(s.decoded_payload for s in run.signals)
        print(f"Block uniformization {payload} -> {restore_block(payload)}")
    print(f"-> {outcome(attempt)}")


def show_stage(stage: Stage) -> None:
    table(
        ("j", "Alice x, p", "Bob x, p", "X_m^2 + P_m^2", "Result"),
        [
            (
                c.index,
                f"{c.alice.real:+.4f}, {c.alice.imag:+.4f}",
                f"{c.bob.real:+.4f}, {c.bob.imag:+.4f}",
                f"{c.statistic:.4f}",
                "pass" if c.passed else "FAIL",
            )
            for c in stage.checks
        ],
    )
    verdict = "passed" if stage.accepted else "failed"
    print(
        f"{failures(stage)} above {EPR_BOUND:g}, rate {stage.failure_rate:.3f} "
        f"vs threshold {stage.threshold:.3f} -> {verdict}"
    )


def show_result(text: str, payload: str, transmission: Transmission) -> None:
    header("Result")
    attempts = transmission.attempts
    finals = transmission.final_attempts
    signals = [s for attempt in attempts for s in attempt.run.signals]
    retries = len(attempts) - len(finals)
    terminated = sum(not a.run.accepted for a in attempts)
    print(f"Sends: {len(attempts)} for {len(finals)} blocks ({retries} retries)")
    print(f"Terminated by the checks: {terminated}")
    print(f"EPR pairs prepared: {sum(a.run.pairs for a in attempts)}")
    raw = sum(hamming_distance(s.box.bits, s.decoded_bits) for s in signals)
    bits = sum(len(s.box.bits) for s in signals)
    print(f"Mapped bit errors: {raw} / {bits}")
    recovered = transmission.recovered_bits
    if recovered is None:
        missing = sum(a.decoded_bits is None for a in finals)
        print(f"No message released: {missing} block(s) failed every send.")
        return
    received = bits_to_bytes(recovered).decode(errors="replace")
    print(
        f"Released bit errors: {hamming_distance(recovered, payload)} / {len(payload)}"
    )
    print(f"Recovered: {received!r} ({'exact' if received == text else 'corrupted'})")


if __name__ == "__main__":
    main()
