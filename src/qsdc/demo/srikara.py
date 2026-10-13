"""Send a text message through the simulated Srikara CV-QSDC protocol.

Prints the settings, one line per send, every protocol step of one block and the
recovered message. --trace adds the noise path of that block's modes.

Simulator presets (presets.yaml):
    baseline   the paper's protocol
    aligned    + measurement along Alice's displacement
    gray       + Gray-labelled intervals
    optimized  + theta in 3pi/2 ± pi/4
    parity     + one parity bit per symbol
    retry      + up to 3 sends per block (optimized + EC, the default)

Examples:
    srikara-demo "hello"
    srikara-demo "hello" --simulator baseline --noise clean
    srikara-demo "hello" --noise metro_10km --block 3 --trace
"""

from __future__ import annotations

import argparse
from cmath import polar
from math import pi, sqrt

from strawberryfields import Engine, Program, ops

from qsdc.common.coding.bits import bits_to_bytes, bytes_to_bits, hamming_distance
from qsdc.common.coding.error_correction import secded_decode, secded_encode
from qsdc.common.config.noise import Detector
from qsdc.common.quadrature import Quadrature
from qsdc.protocols.srikara.config import NOISES, PRESETS, SimulatorConfig
from qsdc.protocols.srikara.constants import MESSAGE_DIRECTION, VACUUM_VARIANCE
from qsdc.protocols.srikara.simulator.backends import (
    SF_SCALE,
    AnalyticBackend,
    PreparedState,
)
from qsdc.protocols.srikara.simulator.encoding import INTERVAL_CODES
from qsdc.protocols.srikara.simulator.protocol import (
    Attempt,
    Check,
    Message,
    SrikaraSimulator,
    Transmission,
)
from qsdc.protocols.srikara.simulator.transport import odd_parity

from .console import header, interval, step, table


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="srikara-demo",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("message", nargs="?", default="hello")
    parser.add_argument("--simulator", choices=list(PRESETS), default="retry")
    parser.add_argument("--noise", choices=list(NOISES), default="lab")
    parser.add_argument("--backend", choices=("analytic", "sf", "sf-sampled"))
    parser.add_argument("--random-source", choices=("classical", "sf-bs-qrng"))
    parser.add_argument("--seed", type=int)
    parser.add_argument(
        "--block", type=int, help="block to show in detail (default: most sends)"
    )
    parser.add_argument(
        "--trace", action="store_true", help="noise path of the detailed block's modes"
    )

    args = parser.parse_args()
    if not args.message:
        parser.error("the message must not be empty")

    update = {"noise": NOISES[args.noise]}
    for field in ("backend", "random_source", "seed"):
        if getattr(args, field) is not None:
            update[field] = getattr(args, field)
    config = PRESETS[args.simulator].model_copy(update=update)

    payload = bytes_to_bits(args.message.encode())
    transmission = SrikaraSimulator(config).transmit(payload)
    blocks = group_by_block(transmission)

    show_settings(config, args.simulator, args.noise)
    print(
        f"\n{args.message!r} -> {len(payload)} bits -> {len(blocks)} blocks, "
        f"{len(transmission.attempts[0].run.states)} states per send"
    )
    show_sends(blocks)

    number = args.block if args.block is not None else most_eventful(blocks)
    trace = args.trace and config.backend != "analytic"
    for attempt in blocks[number]:
        show_attempt(attempt, number, config, trace)

    show_result(args.message, payload, transmission)


def group_by_block(transmission: Transmission) -> list[list[Attempt]]:
    blocks: dict[int, list[Attempt]] = {}
    for attempt in transmission.attempts:
        blocks.setdefault(attempt.block.offset, []).append(attempt)

    return list(blocks.values())


def most_eventful(blocks: list[list[Attempt]]) -> int:
    def score(sends: list[Attempt]) -> tuple[int, int]:
        return len(sends), sum(not m.correct for m in sends[-1].run.messages)

    return max(range(len(blocks)), key=lambda number: score(blocks[number]))


def show_settings(config: SimulatorConfig, simulator: str, noise: str) -> None:
    header(f"Simulator '{simulator}', noise '{noise}'")
    table(
        ("Setting", "Value"),
        [
            ("Backend", config.backend),
            ("Random source", f"{config.random_source} (seed {config.seed})"),
            ("alpha", f"Re, Im Gaussian, variance {config.alpha_variance_snu:g} SNU"),
            ("Squeezing r", str(config.squeeze_r)),
            ("Squeezing angle theta / pi", str(config.theta_pi)),
            ("Intervals", config.intervals),
            ("Measured quadrature", config.axis_policy),
            ("Check tolerance", f"{config.tolerance_sigmas:g} sigma"),
            ("Error correction", config.error_correction),
            ("Sends per block", f"at most {config.max_attempts}"),
        ],
    )

    n = config.noise
    print(
        f"\nFibre T = {n.forward.transmittance:g} / {n.backward.transmittance:g} "
        f"(nbar {n.forward.nbar:g} / {n.backward.nbar:g}), memory T = {n.memory.transmittance:.4g}, "
        f"detector eta = {n.bob_detector.efficiency:g}, v_el = {n.bob_detector.electronic_variance:g} SNU"
        + (" (ignored by the analytic backend)" if config.backend == "analytic" else "")
    )


def show_sends(blocks: list[list[Attempt]]) -> None:
    header("Sends")

    rows = []
    for number, sends in enumerate(blocks):
        block = sends[0].block
        for attempt in sends:
            run = attempt.run
            checks = run.controls + run.decoys
            first = attempt.number == 0
            rows.append(
                (
                    number if first else "",
                    block.bits if first else "",
                    attempt.number + 1,
                    " ".join(m.sent_bits for m in run.messages) or "-",
                    " ".join(m.decoded_bits for m in run.messages) or "-",
                    f"{sum(not c.passed for c in checks)}/{len(checks)}",
                    outcome(attempt),
                )
            )

    table(("Block", "Bits", "Send", "Sent", "Decoded", "Failed checks", "Result"), rows)


def outcome(attempt: Attempt) -> str:
    if attempt.run.aborted:
        return "aborted by the control check"

    if not attempt.run.accepted:
        return "rejected by the decoy check"

    if attempt.decoded_bits is None:
        return "error detected, withheld"

    errors = hamming_distance(attempt.decoded_bits, attempt.block.bits)
    return "released" if not errors else f"released, {errors} wrong bit(s)"


def show_attempt(
    attempt: Attempt, number: int, config: SimulatorConfig, trace: bool
) -> None:
    run, route = attempt.run, attempt.run.route
    code = INTERVAL_CODES[config.intervals]
    header(f"Block {number}, send {attempt.number + 1}")

    roles = {
        **{i: "control" for i in route.control},
        **{i: "message" for i in route.message},
        **{i: "decoy" for i in route.decoy},
    }

    step("1. Bob prepares S(s) D(alpha)|0> and sends every state to Alice")
    table(
        ("j", "Role (secret)", "alpha", "r", "theta / pi"),
        [
            (
                s.index,
                roles[s.index],
                cplx(s.alpha),
                f"{s.squeeze_r:.4f}",
                f"{s.theta / pi:.4f}",
            )
            for s in run.states
        ],
    )

    step("2. Alice checks the control modes after Bob reveals their s and alpha")
    show_checks(run.controls, config)
    if trace:
        for check in run.controls:
            trace_check(run.states[check.index], check, config, "control")

    if run.aborted:
        failed = sum(not c.passed for c in run.controls)
        print(f"{failed} of {len(run.controls)} control checks failed")
        print(f"-> {outcome(attempt)}, Alice sends nothing back")
        return

    step("3. Alice displaces the message modes by m (1 + i), decoys stay unchanged")
    table(
        ("j", "Bits", "Interval", "m"),
        [
            (
                m.index,
                m.sent_bits,
                interval(*code.interval(m.sent_bits)),
                f"{m.value:+.4f}",
            )
            for m in run.messages
        ],
    )

    step("4. Bob checks the decoy modes after Alice reveals them")
    show_checks(run.decoys, config)
    if trace:
        for check in run.decoys:
            trace_check(run.states[check.index], check, config, "decoy")

    checks = run.controls + run.decoys
    print(
        f"{sum(not c.passed for c in checks)} of {len(checks)} checks failed -> "
        + ("accepted" if run.accepted else "rejected")
    )

    step(
        "5. Bob unsqueezes the message modes and decodes m = (x - baseline) / response"
    )
    table(
        ("j", "Delta", "Axis", "x", "Baseline", "Response", "m", "Bits", "Sent"),
        [
            (
                m.index,
                cplx(
                    AnalyticBackend.unsqueezed_displacement(
                        m.value * MESSAGE_DIRECTION,
                        run.states[m.index].squeeze_r,
                        run.states[m.index].theta,
                    )
                ),
                m.axis.name,
                f"{m.measured:+.4f}",
                f"{m.baseline:+.4f}",
                f"{m.response:+.4f}",
                f"{m.decoded_value:+.4f}",
                m.decoded_bits,
                m.sent_bits,
            )
            for m in run.messages
        ],
    )
    if trace:
        for message in run.messages:
            trace_message(run.states[message.index], message, config)

    if run.accepted:
        show_code(attempt, config)

    print(f"-> {outcome(attempt)}")


def show_checks(checks: tuple[Check, ...], config: SimulatorConfig) -> None:
    table(
        ("j", "Axis", "Expected", "Sigma", "Measured", "|dev| / sigma", "Result"),
        [
            (
                c.index,
                c.axis.name,
                f"{c.expected:+.4f}",
                f"{c.sigma:.4f}",
                f"{c.measured:+.4f}",
                f"{abs(c.measured - c.expected) / c.sigma:.3f}" if c.sigma else "exact",
                "pass" if c.passed else "FAIL",
            )
            for c in checks
        ],
    )


def show_code(attempt: Attempt, config: SimulatorConfig) -> None:
    received = [m.decoded_bits for m in attempt.run.messages]

    if config.error_correction == "parity":
        word, odd = received[0], odd_parity(attempt.block.offset)
        ones = word.count("1")
        verdict = "passes" if ones % 2 == odd else "error detected"
        print(f"{'Odd' if odd else 'Even'} parity of {word}: {ones} ones, {verdict}")

    if config.error_correction == "secded":
        for lane, word in enumerate("".join(column) for column in zip(*received)):
            data = secded_decode(word)
            if data is None:
                print(f"Codeword {lane}: {word} -> uncorrectable")
                continue

            flips = hamming_distance(word, secded_encode(data))
            print(f"Codeword {lane}: {word} -> data {data} ({flips} bit(s) corrected)")


def trace_check(
    state: PreparedState, check: Check, config: SimulatorConfig, kind: str
) -> None:
    print(f"\n  Noise path of {kind} mode {check.index}, {check.axis.name} quadrature:")

    if kind == "control":
        detector = config.noise.alice_detector
        stages = control_stages(state, config)
    else:
        detector = config.noise.bob_detector
        stages = returned_stages(state, 0j, config)

    trace_stages(stages, check.axis, detector)


def trace_message(
    state: PreparedState, message: Message, config: SimulatorConfig
) -> None:
    print(
        f"\n  Noise path of message mode {message.index}, {message.axis.name} quadrature:"
    )
    stages = returned_stages(state, message.value * MESSAGE_DIRECTION, config)
    trace_stages(stages, message.axis, config.noise.bob_detector)


def prepare_stages(
    state: PreparedState, config: SimulatorConfig
) -> list[tuple[str, object]]:
    forward = config.noise.forward

    return [
        (f"Bob displaces D({cplx(state.alpha)})", ops.Dgate(*polar(state.alpha))),
        (
            f"Bob squeezes S(s), r = {state.squeeze_r:.4f}",
            ops.Sgate(-state.squeeze_r, state.theta),
        ),
        (
            f"Channel to Alice, T = {forward.transmittance:g}, nbar {forward.nbar:g}",
            ops.ThermalLossChannel(forward.transmittance, forward.nbar),
        ),
    ]


def control_stages(
    state: PreparedState, config: SimulatorConfig
) -> list[tuple[str, object]]:
    detector = config.noise.alice_detector

    return [
        *prepare_stages(state, config),
        ("Alice unsqueezes S(-s)", ops.Sgate(state.squeeze_r, state.theta)),
        (
            f"Alice's detector, eta = {detector.efficiency:g}",
            ops.LossChannel(detector.efficiency),
        ),
    ]


def returned_stages(
    state: PreparedState, beta: complex, config: SimulatorConfig
) -> list[tuple[str, object]]:
    noise = config.noise
    memory, backward = noise.memory, noise.backward

    return [
        *prepare_stages(state, config),
        (
            f"Alice's memory, T = {memory.transmittance:.4f}, nbar {memory.nbar:g}",
            ops.ThermalLossChannel(memory.transmittance, memory.nbar),
        ),
        (
            f"Alice displaces D({cplx(beta)})" if beta else "Alice leaves the decoy",
            ops.Dgate(*polar(beta)),
        ),
        (
            f"Channel to Bob, T = {backward.transmittance:g}, nbar {backward.nbar:g}",
            ops.ThermalLossChannel(backward.transmittance, backward.nbar),
        ),
        ("Bob unsqueezes S(-s)", ops.Sgate(state.squeeze_r, state.theta)),
        (
            f"Bob's detector, eta = {noise.bob_detector.efficiency:g}",
            ops.LossChannel(noise.bob_detector.efficiency),
        ),
    ]


def trace_stages(
    stages: list[tuple[str, object]], axis: Quadrature, detector: Detector
) -> None:
    # Run the circuit up to each stage, and read the quadrature after it.
    rows = []
    for count in range(1, len(stages) + 1):
        program = Program(1)
        with program.context as q:
            for _, operation in stages[:count]:
                operation | q[0]

        mean, variance = (
            Engine("gaussian").run(program).state.quad_expectation(0, axis.angle)
        )
        rows.append(
            (
                stages[count - 1][0],
                f"{mean / SF_SCALE:+.4f}",
                f"{variance / SF_SCALE**2:.4f}",
            )
        )

    final = variance / SF_SCALE**2 + detector.electronic_variance * VACUUM_VARIANCE
    rows.append(
        (f"Electronic noise, {detector.electronic_variance:g} SNU", "", f"{final:.4f}")
    )

    table(("Stage", "Mean", "Variance"), rows, indent="    ")
    print(f"    sigma = {sqrt(final):.4f}")


def show_result(text: str, payload: str, transmission: Transmission) -> None:
    header("Result")
    attempts = transmission.attempts
    finals = transmission.final_attempts
    messages = [m for attempt in attempts for m in attempt.run.messages]

    retries = len(attempts) - len(finals)
    print(f"Sends: {len(attempts)} for {len(finals)} blocks ({retries} retries)")
    print(f"States prepared: {sum(len(a.run.states) for a in attempts)}")

    raw = sum(hamming_distance(m.sent_bits, m.decoded_bits) for m in messages)
    print(f"Symbol bit errors: {raw} / {3 * len(messages)}")

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


def cplx(value: complex) -> str:
    return f"{value.real:+.4f}{value.imag:+.4f}i"


if __name__ == "__main__":
    main()
