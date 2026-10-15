from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, fields
from math import isqrt, log2

from qsdc.common.coding.bits import hamming_distance
from qsdc.common.transmission import Transmission

RATES = (
    "bit_error_rate",
    "raw_bit_error_rate",
    "erasure_rate",
    "delivered_fraction",
    "delivered_bits_per_state",
    "information_per_state",
    "check_failure_rate",
    "coding_rejection_rate",
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
    aborted_attempts: int
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
    def alphabet(self) -> int:
        # The number of symbols. There is one count per sent and decoded pair.
        return isqrt(len(self.symbol_counts))

    @property
    def information_per_symbol(self) -> float:
        # Mutual information between the sent and the decoded symbol.
        n = self.alphabet
        total = sum(self.symbol_counts)
        sent = [sum(self.symbol_count(s, d) for d in range(n)) for s in range(n)]
        decoded = [sum(self.symbol_count(s, d) for s in range(n)) for d in range(n)]

        information = 0.0
        for s in range(n):
            for d in range(n):
                count = self.symbol_count(s, d)
                if count:
                    ratio = count * total / (sent[s] * decoded[d])
                    information += count / total * log2(ratio)

        return information

    @property
    def information_per_state(self) -> float:
        return self.information_per_symbol * sum(self.symbol_counts) / self.states

    @property
    def check_failure_rate(self) -> float:
        return self.failed_checks / self.checks

    @property
    def coding_rejection_rate(self) -> float:
        return self.uncorrectable / (self.blocks + self.retries)

    def symbol_count(self, sent: int, decoded: int) -> int:
        return self.symbol_counts[self.alphabet * sent + decoded]

    def as_dict(self) -> dict[str, object]:
        rates = {rate: getattr(self, rate) for rate in RATES}
        return {**asdict(self), "delivered_bits": self.delivered_bits, **rates}

    @classmethod
    def from_dict(cls, values: dict) -> RunMetrics:
        counts = {field.name: values[field.name] for field in fields(cls)}
        counts["symbol_counts"] = tuple(counts["symbol_counts"])
        return cls(**counts)

    @classmethod
    def pool(cls, metrics: Sequence[RunMetrics]) -> RunMetrics:
        totals = {
            field.name: sum(getattr(m, field.name) for m in metrics)
            for field in fields(cls)
            if field.name != "symbol_counts"
        }

        columns = zip(*(m.symbol_counts for m in metrics))
        counts = tuple(sum(column) for column in columns)

        return cls(**totals, symbol_counts=counts)


def count_blocks(transmission: Transmission) -> dict[str, int]:
    attempts = transmission.attempts
    finals = transmission.final_runs
    released = [run for run in finals if run.decoded_bits is not None]

    return {
        "payload_bits": sum(len(run.block.bits) for run in finals),
        "error_bits": sum(
            hamming_distance(run.block.bits, run.decoded_bits) for run in released
        ),
        "erased_bits": sum(len(r.block.bits) for r in finals if r.decoded_bits is None),
        "blocks": len(finals),
        "retries": len(transmission.runs) - len(finals),
        "aborted_attempts": sum(not a.accepted for a in attempts),
        "uncorrectable": sum(
            run.decoded_bits is None
            for attempt in attempts
            if attempt.accepted
            for run in attempt.runs
        ),
    }


def count_symbols(symbols: Iterable[tuple[str, str]], width: int) -> tuple[int, ...]:
    # How often each sent symbol of width bits was decoded as each symbol.
    n = 2**width
    counts = [0] * (n * n)
    for sent, decoded in symbols:
        counts[n * int(sent, 2) + int(decoded, 2)] += 1

    return tuple(counts)
