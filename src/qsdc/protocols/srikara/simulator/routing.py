from __future__ import annotations

from dataclasses import dataclass

from qsdc.common.random import RandomSource


@dataclass(frozen=True)
class ModeRoute:
    control: tuple[int, ...]
    delayed: tuple[int, ...]
    message: tuple[int, ...]
    decoy: tuple[int, ...]

    @classmethod
    def create(cls, n_states: int, rng: RandomSource) -> ModeRoute:
        shuffled = rng.shuffled(range(n_states))
        control, delayed = shuffled[: n_states // 2], shuffled[n_states // 2 :]

        # Half of the delayed states carry messages, the other half are decoys.
        released = rng.shuffled(delayed)

        return cls(
            control=tuple(sorted(control)),
            delayed=tuple(sorted(delayed)),
            message=tuple(sorted(released[: n_states // 4])),
            decoy=tuple(sorted(released[n_states // 4 :])),
        )
