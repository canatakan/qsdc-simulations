from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Generic, TypeVar

from .random import derive_seed


@dataclass(frozen=True)
class Block:
    offset: int
    bits: str


BlockT = TypeVar("BlockT", bound=Block)
RunT = TypeVar("RunT")


@dataclass(frozen=True)
class Attempt(Generic[BlockT, RunT]):
    block: BlockT
    number: int
    run: RunT
    decoded_bits: str | None


@dataclass(frozen=True)
class Transmission(Generic[BlockT, RunT]):
    attempts: tuple[Attempt[BlockT, RunT], ...]

    @property
    def final_attempts(self) -> list[Attempt[BlockT, RunT]]:
        return list(
            {attempt.block.offset: attempt for attempt in self.attempts}.values()
        )

    @property
    def recovered_bits(self) -> str | None:
        decoded = [attempt.decoded_bits for attempt in self.final_attempts]
        return None if None in decoded else "".join(decoded)


def send_blocks(
    blocks: Iterable[BlockT],
    seed: int,
    max_attempts: int,
    send: Callable[[BlockT, int], tuple[RunT, str | None]],
) -> Transmission[BlockT, RunT]:
    attempts = []
    for block_index, block in enumerate(blocks):
        for number in range(max_attempts):
            run, decoded = send(block, derive_seed(seed, block_index, number))
            attempts.append(Attempt(block, number, run, decoded))
            if decoded is not None:
                break
    return Transmission(tuple(attempts))
