"""Send a text message through the simulated Cao et al. CV-QSDC protocol.

Prints the settings, one line per send, every protocol step of one block and the
recovered message. --noise picks a noise baseline; the default, clean, leaves
only the vacuum noise of the squeezed states and of the measurements. A block
has hundreds of boxes, so the tables show the first --rows of them.

Examples:
    cao-demo "hello"
    cao-demo "hello" --noise lab --rows 12
    cao-demo "hello" --noise metro_10km --max-attempts 3
    cao-demo "hello" --no-reconciliation
"""

from __future__ import annotations

import argparse
from math import e, log10, sqrt

from pydantic import ValidationError

from qsdc.common.coding.bits import bits_to_bytes, bytes_to_bits, hamming_distance
from qsdc.protocols.cao.config import (
    NOISES,
    SYNDROME_FRACTIONS,
    Reconciliation,
    SimulatorConfig,
)
from qsdc.protocols.cao.constants import EPR_BOUND
from qsdc.protocols.cao.simulator.mapping import interval_code, restore_block
from qsdc.protocols.cao.simulator.protocol import (
    Attempt,
    CaoSimulator,
    Stage,
    Transmission,
)

from .console import header, interval, step, table


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cao-demo",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("message", nargs="?", default="hello")
    parser.add_argument("--noise", choices=list(NOISES), default="clean")
    parser.add_argument("--backend", choices=("analytic", "sf", "sf-sampled"))
    parser.add_argument("--random-source", choices=("classical", "sf-bs-qrng"))
    parser.add_argument("--seed", type=int)
    parser.add_argument("--squeeze-r", type=float)
    parser.add_argument("--check-pairs", type=int, help="pairs per check stage")
    parser.add_argument("--max-attempts", type=int, help="sends per block")
    parser.add_argument(
        "--no-reconciliation",
        action="store_true",
        help="release a block only when every box decodes correctly on its own",
    )
    parser.add_argument(
        "--syndrome-fraction",
        type=float,
        help="syndrome bits per payload bit (default: the noise baseline's value)",
    )
    parser.add_argument(
        "--block", type=int, help="block to show in detail (default: most sends)"
    )
    parser.add_argument(
        "--rows", type=int, default=8, help="boxes and checks shown per table"
    )

    args = parser.parse_args()
    if not args.message:
        parser.error("the message must not be empty")

    fields = (
        "backend",
        "random_source",
        "seed",
        "squeeze_r",
        "check_pairs",
        "max_attempts",
    )
    update = {f: getattr(args, f) for f in fields if getattr(args, f) is not None}

    if args.no_reconciliation:
        update["reconciliation"] = None
    else:
        # Each noise baseline has its own syndrome fraction, unless one is given.
        fraction = args.syndrome_fraction
        if fraction is None:
            fraction = SYNDROME_FRACTIONS.get(args.noise)
        if fraction is not None:
            update["reconciliation"] = Reconciliation(syndrome_fraction=fraction)

    try:
        config = SimulatorConfig(noise=NOISES[args.noise], **update)
    except ValidationError as error:
        parser.error(str(error.errors()[0]["msg"]))

    payload = bytes_to_bits(args.message.encode())
    transmission = CaoSimulator(config).transmit(payload)
    blocks = group_by_block(transmission)

    show_settings(config, args.noise)
    print(
        f"\n{args.message!r} -> {len(payload)} bits -> {len(blocks)} blocks, "
        f"{transmission.attempts[0].run.pairs} EPR pairs per send"
    )
    show_sends(blocks)

    number = args.block if args.block is not None else most_eventful(blocks)
    for attempt in blocks[number]:
        show_attempt(attempt, number, config, args.rows)

    show_result(args.message, payload, transmission)


def group_by_block(transmission: Transmission) -> list[list[Attempt]]:
    blocks: dict[int, list[Attempt]] = {}
    for attempt in transmission.attempts:
        blocks.setdefault(attempt.block.offset, []).append(attempt)

    return list(blocks.values())


def most_eventful(blocks: list[list[Attempt]]) -> int:
    def score(sends: list[Attempt]) -> tuple[int, int]:
        return len(sends), wrong_boxes(sends[-1])

    return max(range(len(blocks)), key=lambda number: score(blocks[number]))


def wrong_boxes(attempt: Attempt) -> int:
    return sum(not s.correct for s in attempt.run.signals)


def show_settings(config: SimulatorConfig, noise: str) -> None:
    header(f"Cao et al., noise '{noise}'")
    width = config.box_bits + config.detection_bits
    settings = config.reconciliation

    table(
        ("Setting", "Value"),
        [
            ("Backend", config.backend),
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
            ("Check tolerance", f"{config.check_tolerance_sigmas:g} sigma"),
            (
                "Reconciliation",
                "off"
                if settings is None
                else f"LDPC syndrome of {settings.syndrome_fraction:g} x "
                f"{config.payload_bits} payload bits, column weight "
                f"{settings.column_weight}",
            ),
            (
                "Privacy amplification",
                "off, the paper's uniformization"
                if settings is None
                else f"{config.payload_bits} payload bits - {config.boxes} parities "
                f"- {config.syndrome_bits} syndrome - {settings.secrecy_margin} margin "
                f"= {config.block_bits} message bits",
            ),
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
                    shortened(block.bits, 16) if first else "",
                    attempt.number + 1,
                    failures(run.channel),
                    failures(run.authentication) if run.authentication else "",
                    f"{wrong_boxes(attempt)}/{len(run.signals)}" if run.signals else "",
                    outcome(attempt),
                )
            )

    table(
        ("Block", "Bits", "Send", "Channel", "Auth", "Wrong boxes", "Result"),
        rows,
    )


def failures(stage: Stage) -> str:
    return f"{stage.failed}/{len(stage.checks)}"


def outcome(attempt: Attempt) -> str:
    run = attempt.run
    if not run.accepted:
        return "terminated"

    if attempt.decoded_bits is None:
        if run.syndrome is not None:
            return "reconciliation failed, withheld"
        return "error detected, withheld"

    errors = hamming_distance(attempt.decoded_bits, attempt.block.bits)
    return "released" if not errors else f"released, {errors} wrong bit(s)"


def show_attempt(
    attempt: Attempt, number: int, config: SimulatorConfig, rows: int
) -> None:
    run, block = attempt.run, attempt.block
    code = interval_code(config)
    header(f"Block {number}, send {attempt.number + 1}")

    step("1. Alice prepares EPR pairs (Eqs. 1-4) and sends S2 of each to Bob")
    print(
        f"{run.pairs} pairs: {2 * config.check_pairs} for the checks, "
        f"{config.boxes} for the boxes"
    )

    step("2. Channel detection: both heterodyne the positions Alice picks (Eq. 5)")
    show_stage(run.channel, rows)

    if run.authentication is not None:
        step("3. Authentication: the same test on positions Bob picks")
        show_stage(run.authentication, rows)

    if not run.accepted:
        print("-> communication terminated")
        return

    signals = run.signals
    step("4. Gaussian mapping")
    payloads = "".join(s.box.payload for s in signals)
    print(f"Message bits            {shortened(block.bits)}")
    if block.payload is not None:
        print(
            f"Privacy amplification   {len(payloads) - config.block_bits} random bits "
            f"added, payload chosen so that its hash is the message"
        )
        print(f"Payload                 {shortened(payloads)}")
    else:
        print(f"Message uniformization  {shortened(block.uniformized)}")
        print(f"Block uniformization    {shortened(payloads)}")

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
            for i, s in enumerate(signals[:rows])
        ],
    )
    more(signals, rows)

    step("5. Alice displaces X of S1 by G1' and P by G2, sends S_info to Bob")
    table(
        ("j", "Mapped", "G1'", "G2"),
        [(s.index, s.box.bits, f"{s.g1:+.4f}", f"{s.g2:+.4f}") for s in signals[:rows]],
    )
    more(signals, rows)

    step("6. Bob measures S_info jointly with S2 (Eq. 6)")
    table(
        ("j", "X_m", "P_m"),
        [
            (s.index, f"{s.measured.real:+.4f}", f"{s.measured.imag:+.4f}")
            for s in signals[:rows]
        ],
    )
    more(signals, rows)

    step("7. Postprocessing")

    n = config.noise
    expected = sqrt(n.bob_detector.efficiency * n.channel.transmittance / 2)
    print("(i) Parameter estimation: Alice reveals G2, Bob fits P_m = t G2 + noise")
    print(
        f"    t = {run.estimate.gain:.4f} (expected {expected:.4f}), "
        f"noise variance {run.estimate.noise_variance:.4f} SNU"
    )

    reconciled = run.reconciled
    reconciling = run.syndrome is not None
    if reconciling:
        print(
            f"(ii) Reconciliation: Alice sends a {len(run.syndrome)}-bit LDPC "
            f"syndrome of her {config.payload_bits} payload bits; Bob also uses "
            "the announced detection and parity bits of every box"
        )
    else:
        print("(ii) No reconciliation: every box must pass its detection and parity")

    headers = ("j", "X_m / t", "Decoded", "Mapped", "Detection", "Parity", "Payload")
    if reconciling:
        headers += ("Reconciled",)

    width = config.box_bits
    table_rows = []
    for i, s in enumerate(signals[:rows]):
        row = (
            s.index,
            f"{s.decoded_value:+.4f}",
            s.decoded_bits,
            s.box.bits,
            "ok" if s.detection_valid else "WRONG",
            "ok" if s.parity_valid else "FAIL",
            s.decoded_payload,
        )

        if reconciling:
            corrected = reconciled[i * width : (i + 1) * width] if reconciled else "-"
            row += (corrected,)
        table_rows.append(row)

    table(headers, table_rows)
    more(signals, rows)

    raw = "".join(s.decoded_payload for s in signals)
    print(
        f"Wrong payload bits before reconciliation: "
        f"{hamming_distance(raw, payloads)} / {len(payloads)}"
    )

    if reconciling:
        if reconciled is None:
            print("LDPC decoding did not converge")
        else:
            print(
                "Wrong payload bits after reconciliation: "
                f"{hamming_distance(reconciled, payloads)}"
            )

    if attempt.decoded_bits is not None and reconciled is not None:
        print(
            f"(iii) Privacy amplification: hash of {shortened(reconciled, 24)} -> "
            f"{shortened(attempt.decoded_bits, 24)}"
        )
    elif attempt.decoded_bits is not None:
        print(
            f"(iii) Inverse mapping: {shortened(raw, 24)} -> "
            f"{shortened(restore_block(raw), 24)} -> "
            f"{shortened(attempt.decoded_bits, 24)}"
        )

    print(f"-> {outcome(attempt)}")


def show_stage(stage: Stage, rows: int) -> None:
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
            for c in stage.checks[:rows]
        ],
    )
    more(stage.checks, rows)

    verdict = "passed" if stage.accepted else "failed"
    print(
        f"{failures(stage)} above {EPR_BOUND:g}, rate {stage.failure_rate:.3f} "
        f"vs threshold {stage.threshold:.3f} (honest {stage.expected_failure_rate:.3f}) "
        f"-> {verdict}"
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

    wrong = sum(not s.correct for s in signals)
    print(f"Boxes decoded into a wrong interval: {wrong} / {len(signals)}")
    revealed = sum(len(a.run.syndrome) for a in attempts if a.run.syndrome)
    if revealed:
        print(f"Syndrome bits revealed: {revealed}")

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


def more(items: tuple | list, rows: int) -> None:
    if len(items) > rows:
        print(f"... {len(items) - rows} more")


def shortened(bits: str, limit: int = 48) -> str:
    return bits if len(bits) <= limit else f"{bits[:limit]}... ({len(bits)} bits)"


if __name__ == "__main__":
    main()
