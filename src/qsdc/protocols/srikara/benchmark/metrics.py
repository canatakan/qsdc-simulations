from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, fields
from math import log2

from qsdc.common.coding.bits import hamming_distance

from ..simulator.protocol import Transmission

RATES = (
    "bit_error_rate",
    "raw_bit_error_rate",
    "erasure_rate",
    "delivered_fraction",
    "delivered_bits_per_state",
    "information_per_state",
    "rejection_rate",
    "check_failure_rate",
)


@dataclass(frozen=True)
class RunMetrics:
    payload_bits: int
    error_bits: int
    erased_bits: int
    raw_bits: int
    raw_error_bits: int
    states: int
    blocks: int
    retries: int
    rejected: int
    checks: int
    failed_checks: int
    uncorrectable: int
    seconds: float
    symbol_counts: tuple[int, ...]

    @property
    def delivered_bits(self) -> int:
        return self.payload_bits - self.erased_bits - self.error_bits

    @property
    def bit_error_rate(self) -> float | None:
        released = self.payload_bits - self.erased_bits
        return self.error_bits / released if released else None

    @property
    def raw_bit_error_rate(self) -> float | None:
        return self.raw_error_bits / self.raw_bits if self.raw_bits else None

    @property
    def erasure_rate(self) -> float:
        return self.erased_bits / self.payload_bits

    @property
    def delivered_fraction(self) -> float:
        return self.delivered_bits / self.payload_bits

    @property
    def delivered_bits_per_state(self) -> float:
        return self.delivered_bits / self.states

    @property
    def information_per_symbol(self) -> float:
        # Mutual information between the sent and the decoded symbol.
        total = sum(self.symbol_counts)
        sent = [sum(self.symbol_count(s, d) for d in range(8)) for s in range(8)]
        decoded = [sum(self.symbol_count(s, d) for s in range(8)) for d in range(8)]

        information = 0.0
        for s in range(8):
            for d in range(8):
                count = self.symbol_count(s, d)
                if count:
                    ratio = count * total / (sent[s] * decoded[d])
                    information += count / total * log2(ratio)

        return information

    @property
    def information_per_state(self) -> float:
        return self.information_per_symbol * sum(self.symbol_counts) / self.states

    @property
    def rejection_rate(self) -> float:
        return self.rejected / (self.blocks + self.retries)

    @property
    def check_failure_rate(self) -> float:
        return self.failed_checks / self.checks

    @staticmethod
    def symbol_index(sent: int, decoded: int) -> int:
        # The 64 symbol counts are ordered by sent symbol, then decoded symbol.
        return 8 * sent + decoded

    def symbol_count(self, sent: int, decoded: int) -> int:
        return self.symbol_counts[self.symbol_index(sent, decoded)]

    def as_dict(self) -> dict[str, object]:
        rates = {rate: getattr(self, rate) for rate in RATES}
        return {**asdict(self), "delivered_bits": self.delivered_bits, **rates}

    @classmethod
    def from_dict(cls, values: dict) -> RunMetrics:
        # The inverse of as_dict
        counts = {field.name: values[field.name] for field in fields(cls)}
        counts["symbol_counts"] = tuple(counts["symbol_counts"])
        return cls(**counts)

    @classmethod
    def measure(cls, transmission: Transmission, seconds: float) -> RunMetrics:
        finals = transmission.final_attempts
        released = [attempt for attempt in finals if attempt.decoded_bits is not None]
        messages = [
            m for attempt in transmission.attempts for m in attempt.run.messages
        ]
        checks = [
            check
            for attempt in transmission.attempts
            for check in attempt.run.controls + attempt.run.decoys
        ]

        symbol_counts = [0] * 64
        for m in messages:
            index = cls.symbol_index(int(m.sent_bits, 2), int(m.decoded_bits, 2))
            symbol_counts[index] += 1

        return cls(
            payload_bits=sum(len(attempt.block.bits) for attempt in finals),
            error_bits=sum(
                hamming_distance(a.block.bits, a.decoded_bits) for a in released
            ),
            erased_bits=sum(
                len(a.block.bits) for a in finals if a.decoded_bits is None
            ),
            raw_bits=3 * len(messages),
            raw_error_bits=sum(
                hamming_distance(m.sent_bits, m.decoded_bits) for m in messages
            ),
            states=sum(len(attempt.run.states) for attempt in transmission.attempts),
            blocks=len(finals),
            retries=len(transmission.attempts) - len(finals),
            rejected=sum(not a.run.accepted for a in transmission.attempts),
            checks=len(checks),
            failed_checks=sum(not check.passed for check in checks),
            uncorrectable=sum(
                a.run.accepted and a.decoded_bits is None for a in transmission.attempts
            ),
            seconds=seconds,
            symbol_counts=tuple(symbol_counts),
        )

    @classmethod
    def pool(cls, metrics: Sequence[RunMetrics]) -> RunMetrics:
        # Repetitions are pooled by adding their counts.
        totals = {
            field.name: sum(getattr(m, field.name) for m in metrics)
            for field in fields(cls)
            if field.name != "symbol_counts"
        }

        columns = zip(*(m.symbol_counts for m in metrics))
        counts = tuple(sum(column) for column in columns)

        return cls(**totals, symbol_counts=counts)
