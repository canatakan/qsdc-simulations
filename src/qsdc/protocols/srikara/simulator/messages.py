from __future__ import annotations

from dataclasses import dataclass

from qsdc.common.coding.intervals import IntervalCode
from qsdc.common.quadrature import P, Q, Quadrature
from qsdc.common.random import RandomSource

from ..constants import MESSAGE_DIRECTION
from .backends import Backend, PreparedState
from .checks import AXES


@dataclass(frozen=True)
class Message:
    index: int
    sent_bits: str
    value: float
    axis: Quadrature
    measured: float
    baseline: float
    response: float
    decoded_value: float
    decoded_bits: str

    @property
    def correct(self) -> bool:
        return self.decoded_bits == self.sent_bits


class Receiver:
    def __init__(self, backend: Backend, code: IntervalCode, axis_policy: str):
        self.backend = backend
        self.code = code
        self.axis_policy = axis_policy

    def receive(
        self,
        states: tuple[PreparedState, ...],
        indices: tuple[int, ...],
        symbols: tuple[str, ...],
        values: list[float],
        rng: RandomSource,
    ) -> tuple[Message, ...]:
        messages = []
        for i, bits, value in zip(indices, symbols, values):
            messages.append(self.receive_one(states[i], bits, value, rng))

        return tuple(messages)

    def receive_one(
        self, state: PreparedState, bits: str, value: float, rng: RandomSource
    ) -> Message:
        axis = self.axis(state, rng)

        measured = self.backend.measure_returned(state, axis, value * MESSAGE_DIRECTION)
        baseline = self.backend.expect_returned(state, axis).mean
        response = self.backend.message_response(state, axis)

        # Without any signal reaching Bob, his best guess is m = 0.
        decoded = (measured - baseline) / response if response else 0.0

        return Message(
            state.index,
            bits,
            value,
            axis,
            measured,
            baseline,
            response,
            decoded,
            self.code.decode(decoded),
        )

    def axis(self, state: PreparedState, rng: RandomSource) -> Quadrature:
        if self.axis_policy == "random":
            return rng.choice(AXES)

        response_q = self.backend.message_response(state, Q)
        response_p = self.backend.message_response(state, P)

        if self.axis_policy == "best_qp":
            return Q if abs(response_q) >= abs(response_p) else P

        # aligned: along the message displacement Bob sees after unsqueezing.
        return Quadrature(complex(response_q, response_p))
