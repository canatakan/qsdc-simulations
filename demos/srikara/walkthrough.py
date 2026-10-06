"""Step-by-step printout of a Srikara transmission, shared by the message and noise demos."""

from __future__ import annotations

import textwrap
from cmath import exp, polar
from math import inf, pi, sqrt

from strawberryfields import Engine, Program, ops

from qsdc.common.bits import bits_to_bytes, hamming_distance
from qsdc.common.error_correction import secded_decode, secded_encode
from qsdc.common.quadrature import P, Q, Quadrature
from qsdc.protocols.srikara.config import Detector, SimulatorConfig
from qsdc.protocols.srikara.simulator.backends import (
    SF_SCALE,
    VACUUM_VARIANCE,
    AnalyticBackend,
    Backend,
    PreparedState,
    make_backend,
)
from qsdc.protocols.srikara.simulator.encoding import INTERVAL_CODES, MESSAGE_DIRECTION
from qsdc.protocols.srikara.simulator.protocol import (
    Attempt,
    Check,
    Message,
    Transmission,
)
from qsdc.protocols.srikara.simulator.transport import (
    Block,
    encode_blocks,
    odd_parity,
)


def show_transmission(
    config: SimulatorConfig,
    text: str,
    payload: str,
    transmission: Transmission,
    trace_noise: bool,
) -> None:
    """Print everything from the text message to the recovered text."""
    show_settings(config)
    show_payload(text, payload)
    blocks = encode_blocks(payload, config.error_correction)
    show_blocks(blocks, config)
    block_numbers = {block.offset: number for number, block in enumerate(blocks)}
    for attempt in transmission.attempts:
        show_attempt(attempt, block_numbers[attempt.block.offset], config, trace_noise)
    show_result(text, payload, transmission)


def show_settings(config: SimulatorConfig) -> None:
    header("Simulator settings")
    code = INTERVAL_CODES[config.intervals]
    rows = [
        ("Backend", config.backend),
        ("Protocol random source", f"{config.random_source} (seed {config.seed})"),
        (
            "Displacement alpha",
            f"Re, Im uniform in [-{config.alpha_bound:g}, {config.alpha_bound:g}]",
        ),
        ("Squeezing r", str(config.squeeze_r)),
        ("Squeezing angle theta / pi", str(config.theta_pi)),
        ("Message intervals", config.intervals),
        ("Bob's decoding axis", config.axis_policy),
        ("Check tolerance", f"{config.tolerance_sigmas:g} sigma"),
        ("Error correction", config.error_correction),
        ("Attempts per block", str(config.max_attempts)),
    ]
    table(("Setting", "Value"), rows)

    print("\nInterval code (Alice picks m_A inside the symbol's interval):")
    table(
        ("Bits", "Interval of m_A"),
        [(bits, interval(*code.interval(bits))) for bits in code.labels],
    )

    noise = config.noise
    ignored = (
        " (ignored by the analytic backend)" if config.backend == "analytic" else ""
    )
    print(f"\nNoise model{ignored}:")
    table(
        ("Stage", "Model", "Transmittance", "Thermal nbar", "Extra"),
        [
            (
                "Bob -> Alice",
                "thermal loss",
                f"{noise.forward.transmittance:g}",
                f"{noise.forward.nbar:g}",
                "",
            ),
            (
                "Alice's memory",
                "thermal loss",
                f"{noise.memory.transmittance:.4f}",
                f"{noise.memory.nbar:g}",
                f"eff {noise.memory.efficiency:g} * exp(-{noise.memory.seconds:g} s / {noise.memory.lifetime_seconds:g} s)",
            ),
            (
                "Alice -> Bob",
                "thermal loss",
                f"{noise.backward.transmittance:g}",
                f"{noise.backward.nbar:g}",
                "",
            ),
            (
                "Alice's detector",
                "loss + readout",
                f"{noise.alice_detector.efficiency:g}",
                "0",
                electronic(noise.alice_detector),
            ),
            (
                "Bob's detector",
                "loss + readout",
                f"{noise.bob_detector.efficiency:g}",
                "0",
                electronic(noise.bob_detector),
            ),
        ],
    )
    print(
        f"Quadrature units: vacuum variance = {VACUUM_VARIANCE}, so a coherent state has sigma = 0.5."
    )


def show_payload(text: str, payload: str) -> None:
    header("1. Classical message")
    data = text.encode()
    print(f"Text: {text!r}")
    print(f"UTF-8 bytes ({len(data)}): {data.hex(' ')}")
    print(f"Payload ({len(payload)} bits):")
    wrapped(" ".join(payload[i : i + 8] for i in range(0, len(payload), 8)))


def show_blocks(blocks: list[Block], config: SimulatorConfig) -> None:
    header("2. Transport blocks")
    per_run = f"{4 * len(blocks[0].symbols)} states per protocol run"
    if config.error_correction == "none":
        print(f"Each block carries one 3-bit symbol; {per_run}.")
    elif config.error_correction == "parity":
        print(
            "Parity: each symbol carries 2 payload bits and a parity bit that makes the\n"
            "number of ones odd in one block and even in the next, so every interval is used\n"
            "equally. An odd number of wrong bits is detected (not located).\n"
            f"A block that fails the parity check is withheld and sent again. {per_run}."
        )
    else:
        print(
            "SECDED: every 12 payload bits become three extended Hamming (8, 4) codewords.\n"
            "Symbol k carries bit k of each codeword, so one bad symbol costs each codeword\n"
            f"only one bit, which it can correct. {per_run}."
        )
    for number, block in enumerate(blocks):
        size = {"none": 3, "parity": 2, "secded": 12}[config.error_correction]
        padding = size - len(block.bits)
        print(
            f"\nBlock {number}: payload bits {block.offset}-{block.offset + len(block.bits) - 1} "
            f"= {block.bits}" + (f" (+{padding} zero padding bits)" if padding else "")
        )
        if config.error_correction == "secded":
            padded = block.bits.ljust(12, "0")
            for lane in range(3):
                nibble = padded[4 * lane : 4 * lane + 4]
                print(f"  codeword {lane}: data {nibble} -> {secded_encode(nibble)}")
        print(f"  symbols sent: {' '.join(block.symbols)}")


def show_attempt(
    attempt: Attempt, number: int, config: SimulatorConfig, trace: bool
) -> None:
    run, block = attempt.run, attempt.block
    route = run.route
    code = INTERVAL_CODES[config.intervals]
    header(
        f"Block {number}, attempt {attempt.number + 1} of at most {config.max_attempts}: "
        f"{len(block.symbols)} symbol(s), {len(run.states)} states"
    )
    roles = {
        **{i: "control" for i in route.control},
        **{i: "message" for i in route.message},
        **{i: "decoy" for i in route.decoy},
    }

    step("3. Bob prepares S(s_j) D(alpha_j)|0> and sends every state to Alice")
    table(
        (
            "j",
            "Role (secret)",
            "alpha_j",
            "r_j",
            "theta_j / pi",
            "s_j = r exp(i theta)",
        ),
        [
            (
                state.index,
                roles[state.index],
                cplx(state.alpha),
                f"{state.squeeze_r:.4f}",
                f"{state.theta / pi:.4f}",
                cplx(state.squeeze_r * exp(1j * state.theta)),
            )
            for state in run.states
        ],
    )

    step("4. Alice splits the states with her optical switch")
    print(f"Control modes (n/2), measured now:     {route.control}")
    print(f"Delayed modes (n/2), kept in memory:   {route.delayed}")
    print(f"Alice -> Bob (public): control coordinates {route.control}")
    print("Bob -> Alice (public): s_j and alpha_j for those coordinates")

    step(
        "5. Alice applies S(-s_j), homodynes a random quadrature and checks Re/Im(alpha_j)"
    )
    show_checks(run.controls, config)
    if trace:
        for check in run.controls:
            trace_check(run.states[check.index], check, config, "control")

    step("6. Alice encodes the delayed modes and sends them back")
    print(f"Message modes (n/4): {route.message}")
    print(f"Decoy modes (n/4):   {route.decoy}  (left unchanged)")
    table(
        ("j", "Bits", "Interval", "m_A", "beta_A = m_A (1 + i)"),
        [
            (
                m.index,
                m.sent_bits,
                interval(*code.interval(m.sent_bits)),
                f"{m.value:+.4f}",
                cplx(m.value * MESSAGE_DIRECTION),
            )
            for m in run.messages
        ],
    )

    step(
        "7. Alice -> Bob (public): decoy coordinates; Bob applies S(-s_j) and checks them"
    )
    show_checks(run.decoys, config)
    if trace:
        for check in run.decoys:
            trace_check(run.states[check.index], check, config, "decoy")

    step("8. Acceptance")
    checks = run.controls + run.decoys
    failed = sum(not check.passed for check in checks)
    verdict = "accepted" if run.accepted else "REJECTED: the block is discarded"
    print(f"{failed} of {len(checks)} checks failed; all must pass -> {verdict}")

    step("9. Bob unsqueezes the message modes and decodes m_A")
    show_messages(run.messages, run.states, config)
    if trace:
        for message in run.messages:
            trace_message(run.states[message.index], message, config)

    step("10. Block result")
    show_block_result(attempt, config)


def show_checks(checks: tuple[Check, ...], config: SimulatorConfig) -> None:
    table(
        (
            "j",
            "Axis",
            "Expected",
            "Sigma",
            "Tolerance",
            "Measured",
            "|dev| / sigma",
            "Result",
        ),
        [
            (
                c.index,
                c.axis.name,
                f"{c.expected:+.4f}",
                f"{c.sigma:.4f}",
                f"±{config.tolerance_sigmas * c.sigma:.4f}",
                f"{c.measured:+.4f}",
                f"{abs(c.measured - c.expected) / c.sigma:.3f}" if c.sigma else "exact",
                "pass" if c.passed else "FAIL",
            )
            for c in checks
        ],
    )


def show_messages(
    messages: tuple[Message, ...],
    states: tuple[PreparedState, ...],
    config: SimulatorConfig,
) -> None:
    backend = make_backend(config)
    print(
        "Delta = beta_A cosh r - exp(i theta) beta_A* sinh r is Alice's displacement after S(-s).\n"
        "The response is the shift of Bob's reading per unit m_A, from the backend; on the\n"
        "Strawberry Fields backends it includes the loss on the way back."
    )
    table(
        (
            "j",
            "Delta",
            "resp q",
            "resp p",
            "Axis",
            "Measured",
            "Baseline",
            "(meas - base) / resp",
            "Bits",
            "Sent",
            "",
        ),
        [
            (
                m.index,
                cplx(
                    AnalyticBackend.unsqueezed_displacement(
                        m.value * MESSAGE_DIRECTION,
                        states[m.index].squeeze_r,
                        states[m.index].theta,
                    )
                ),
                response(backend, states[m.index], Q),
                response(backend, states[m.index], P),
                m.axis.name,
                f"{m.measured:+.4f}",
                f"{m.baseline:+.4f}",
                f"{m.decoded_value:+.4f}",
                m.decoded_bits,
                m.sent_bits,
                "ok"
                if m.decoded_bits == m.sent_bits
                else f"{hamming_distance(m.sent_bits, m.decoded_bits)} bit(s) wrong",
            )
            for m in messages
        ],
    )


def show_block_result(attempt: Attempt, config: SimulatorConfig) -> None:
    block, run = attempt.block, attempt.run
    received = [m.decoded_bits for m in run.messages]
    if not run.accepted:
        again = attempt.number + 1 < config.max_attempts
        print(
            "Bob ignores the decoded symbols;",
            "the block is sent again." if again else "no attempts left.",
        )
        return
    print(f"Received symbols: {' '.join(received)}")
    if config.error_correction == "secded":
        for lane, word in enumerate("".join(column) for column in zip(*received)):
            data = secded_decode(word)
            if data is None:
                print(
                    f"  codeword {lane}: {word} -> two or more errors detected, uncorrectable"
                )
                continue
            flips = hamming_distance(word, secded_encode(data))
            note = "clean" if not flips else "1 bit corrected"
            print(
                f"  codeword {lane}: {word} -> nearest {secded_encode(data)} -> data {data} ({note})"
            )
    if config.error_correction == "parity":
        word, odd = received[0], odd_parity(block.offset)
        expected = "odd" if odd else "even"
        passed = word.count("1") % 2 == odd
        verdict = "passes" if passed else "error detected"
        print(f"  {expected} parity of {word}: {word.count('1')} ones, {verdict}")
    if attempt.decoded_bits is None:
        print("The error correction detected an error; the block is not released.")
        return
    errors = hamming_distance(attempt.decoded_bits, block.bits)
    print(f"Released bits: {attempt.decoded_bits}")
    print(f"Sent bits:     {block.bits}  ({errors} wrong)")


def trace_check(
    state: PreparedState, check: Check, config: SimulatorConfig, kind: str
) -> None:
    print(f"\n  Noise path of {kind} mode {check.index}, {check.axis.name} quadrature:")
    detector = (
        config.noise.alice_detector if kind == "control" else config.noise.bob_detector
    )
    stages = (
        control_stages(state, config)
        if kind == "control"
        else returned_stages(state, 0j, config)
    )
    variance = trace_stages(stages, check.axis, detector)
    print(
        f"  Expected {check.expected:+.4f} ± {sqrt(variance):.4f}; measured {check.measured:+.4f} "
        f"-> {'pass' if check.passed else 'FAIL'}"
    )


def trace_message(
    state: PreparedState, message: Message, config: SimulatorConfig
) -> None:
    print(
        f"\n  Noise path of message mode {message.index} ({message.sent_bits}), {message.axis.name} quadrature:"
    )
    beta = message.value * MESSAGE_DIRECTION
    variance = trace_stages(
        returned_stages(state, beta, config), message.axis, config.noise.bob_detector
    )
    print(
        f"  Bob measures {message.measured:+.4f}; without a message he would expect {message.baseline:+.4f} "
        f"(noise sigma {sqrt(variance):.4f}).\n"
        f"  m = ({message.measured:+.4f} - {message.baseline:+.4f}) / {message.response:+.4f} = "
        f"{message.decoded_value:+.4f} -> {message.decoded_bits} (sent m_A = {message.value:+.4f}, {message.sent_bits})"
    )


def control_stages(
    state: PreparedState, config: SimulatorConfig
) -> list[tuple[str, object]]:
    noise = config.noise
    return [
        *prepare_stages(state, config),
        ("Alice unsqueezes S(-s)", ops.Sgate(state.squeeze_r, state.theta)),
        (
            f"Alice's detector, efficiency {noise.alice_detector.efficiency:g}",
            ops.LossChannel(noise.alice_detector.efficiency),
        ),
    ]


def returned_stages(
    state: PreparedState, beta: complex, config: SimulatorConfig
) -> list[tuple[str, object]]:
    noise = config.noise
    memory, backward = noise.memory, noise.backward
    alice = (
        f"Alice displaces D({cplx(beta)})"
        if beta
        else "Alice leaves the decoy unchanged"
    )
    return [
        *prepare_stages(state, config),
        (
            f"Alice's memory, T = {memory.transmittance:.4f}, nbar {memory.nbar:g}",
            ops.ThermalLossChannel(memory.transmittance, memory.nbar),
        ),
        (alice, ops.Dgate(*polar(beta))),
        (
            f"Channel to Bob, T = {backward.transmittance:g}, nbar {backward.nbar:g}",
            ops.ThermalLossChannel(backward.transmittance, backward.nbar),
        ),
        ("Bob unsqueezes S(-s)", ops.Sgate(state.squeeze_r, state.theta)),
        (
            f"Bob's detector, efficiency {noise.bob_detector.efficiency:g}",
            ops.LossChannel(noise.bob_detector.efficiency),
        ),
    ]


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


def trace_stages(
    stages: list[tuple[str, object]], axis: Quadrature, detector: Detector
) -> float:
    """Print the measured quadrature's mean and variance after every stage; return the final variance."""
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
        (
            f"Electronic readout noise, {detector.electronic_variance:g} SNU",
            "",
            f"{final:.4f}",
        )
    )
    table(("Stage", "Mean", "Variance"), rows, indent="    ")
    return final


def show_result(text: str, payload: str, transmission: Transmission) -> None:
    header("11. Reassembled message")
    attempts = transmission.attempts
    messages = [m for attempt in attempts for m in attempt.run.messages]
    finals = transmission.final_attempts
    table(
        ("Quantity", "Value"),
        [
            ("Blocks", len(finals)),
            ("Protocol runs (attempts)", len(attempts)),
            ("Rejected runs", sum(not attempt.run.accepted for attempt in attempts)),
            ("Prepared states", sum(len(attempt.run.states) for attempt in attempts)),
            (
                "Symbol bit errors before correction",
                f"{sum(hamming_distance(m.sent_bits, m.decoded_bits) for m in messages)} / {3 * len(messages)}",
            ),
            (
                "Blocks not released",
                sum(attempt.decoded_bits is None for attempt in finals),
            ),
        ],
    )
    recovered = transmission.recovered_bits
    if recovered is None:
        missing = [
            attempt.block.offset for attempt in finals if attempt.decoded_bits is None
        ]
        print(
            f"\nNo message released: blocks at payload bits {missing} were never recovered."
        )
        return
    errors = [i for i, (a, b) in enumerate(zip(payload, recovered)) if a != b]
    print("\nRecovered payload:")
    wrapped(" ".join(recovered[i : i + 8] for i in range(0, len(recovered), 8)))
    print(f"Wrong bits: {len(errors)}" + (f" at positions {errors}" if errors else ""))
    received = bits_to_bytes(recovered).decode(errors="replace")
    print(
        f"Recovered text: {received!r} ({'exact' if received == text else 'corrupted'})"
    )


def header(title: str) -> None:
    print(f"\n{'=' * len(title)}\n{title}\n{'=' * len(title)}")


def step(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


def table(
    headers: tuple[str, ...], rows: list[tuple[object, ...]], indent: str = ""
) -> None:
    cells = [tuple(str(cell) for cell in row) for row in rows]
    widths = [
        max(len(str(h)), *(len(row[i]) for row in cells)) for i, h in enumerate(headers)
    ]
    for row in (headers, tuple("-" * w for w in widths), *cells):
        print(
            (indent + "  ".join(cell.ljust(w) for cell, w in zip(row, widths))).rstrip()
        )


def wrapped(text: str) -> None:
    for line in textwrap.wrap(text, 72):
        print(f"  {line}")


def cplx(value: complex) -> str:
    return f"{value.real:+.4f}{value.imag:+.4f}i"


def interval(lower: float, upper: float) -> str:
    left = "-inf" if lower == -inf else f"{lower:.4g}"
    right = "inf" if upper == inf else f"{upper:.4g}"
    return f"[{left}, {right})"


def electronic(detector: Detector) -> str:
    variance = detector.electronic_variance
    return (
        f"electronic {variance:g} SNU = variance {variance * VACUUM_VARIANCE:g}"
        if variance
        else ""
    )


def response(backend: Backend, state: PreparedState, axis: Quadrature) -> str:
    return f"{backend.message_response(state, axis):+.4f}"
