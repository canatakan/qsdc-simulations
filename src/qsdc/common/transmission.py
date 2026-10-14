from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from math import sqrt
from typing import Generic, TypeVar

from .config.base import BaseSimulatorConfig
from .random import derive_seed


@dataclass(frozen=True)
class BaseBlock:
    offset: int
    bits: str


BlockT = TypeVar("BlockT", bound=BaseBlock)


@dataclass(frozen=True)
class BaseRun(Generic[BlockT]):
    block: BlockT
    decoded_bits: str | None


RunT = TypeVar("RunT", bound=BaseRun)


@dataclass(frozen=True)
class SecurityTest:
    checks: int
    failed: int
    expected_failure_rate: float
    threshold: float

    @classmethod
    def judge(
        cls, checks: Sequence, expected_failure_rate: float, tolerance_sigmas: float
    ) -> SecurityTest:
        rate = expected_failure_rate
        margin = sqrt(rate * (1 - rate) / len(checks))

        return cls(
            len(checks),
            sum(not check.passed for check in checks),
            rate,
            rate + tolerance_sigmas * margin,
        )

    @property
    def failure_rate(self) -> float:
        return self.failed / self.checks

    @property
    def passed(self) -> bool:
        return self.failure_rate <= self.threshold


@dataclass(frozen=True)
class BaseAttempt(Generic[RunT]):
    number: int
    security_tests: tuple[SecurityTest, ...]
    runs: tuple[RunT, ...]

    @property
    def accepted(self) -> bool:
        return all(test.passed for test in self.security_tests)


AttemptT = TypeVar("AttemptT", bound=BaseAttempt)


@dataclass(frozen=True)
class Transmission(Generic[AttemptT]):
    attempts: tuple[AttemptT, ...]

    @property
    def runs(self) -> list[BaseRun]:
        return [run for attempt in self.attempts for run in attempt.runs]

    @property
    def final_runs(self) -> list[BaseRun]:
        return list({run.block.offset: run for run in self.runs}.values())

    @property
    def recovered_bits(self) -> str | None:
        decoded = [run.decoded_bits for run in self.final_runs]
        return None if None in decoded else "".join(decoded)


class BaseSimulator(ABC, Generic[BlockT, AttemptT]):
    config: BaseSimulatorConfig

    @abstractmethod
    def encode(self, payload: str) -> list[BlockT]: ...

    @abstractmethod
    def run_attempt(self, blocks: list[BlockT], number: int, seed: int) -> AttemptT: ...

    def transmit(self, payload: str) -> Transmission[AttemptT]:
        if not payload or set(payload) - {"0", "1"}:
            raise ValueError("payload must be a non-empty string of 0s and 1s")

        config = self.config
        attempts = []
        pending = self.encode(payload)
        for number in range(config.max_attempts):
            attempt = self.run_attempt(
                pending, number, derive_seed(config.seed, number)
            )
            attempts.append(attempt)

            pending = [run.block for run in attempt.runs if run.decoded_bits is None]
            if not pending:
                break

        return Transmission(tuple(attempts))
