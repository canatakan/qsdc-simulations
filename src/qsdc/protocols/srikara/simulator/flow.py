"""Protocol-flow abstractions for routing and public announcements."""

from __future__ import annotations

from dataclasses import dataclass

from qsdc.common.random.base import RandomSource


@dataclass(frozen=True)
class ModeRoute:
    control_indices: tuple[int, ...]
    delayed_indices: tuple[int, ...]
    message_indices: tuple[int, ...]
    decoy_indices: tuple[int, ...]


@dataclass(frozen=True)
class PublicAnnouncement:
    label: str
    indices: tuple[int, ...]


@dataclass(frozen=True)
class ProtocolTranscript:
    random_source: str
    control_coordinates: PublicAnnouncement
    control_parameter_coordinates: PublicAnnouncement
    decoy_coordinates: PublicAnnouncement


class OpticalSwitch:
    """Routes modes according to the protocol QRNG choices."""

    def __init__(self, random_source: RandomSource):
        self._random_source = random_source

    def route(self, n_states: int) -> ModeRoute:
        shuffled_indices = self._random_source.shuffled(range(n_states))
        half = n_states // 2
        quarter = n_states // 4

        control_indices = tuple(sorted(shuffled_indices[:half]))
        delayed_indices = tuple(shuffled_indices[half:])

        released_indices = self._random_source.shuffled(delayed_indices)
        message_indices = tuple(sorted(released_indices[:quarter]))
        decoy_indices = tuple(sorted(released_indices[quarter:]))

        return ModeRoute(
            control_indices=control_indices,
            delayed_indices=tuple(sorted(delayed_indices)),
            message_indices=message_indices,
            decoy_indices=decoy_indices,
        )


def build_transcript(
    route: ModeRoute,
    random_source: RandomSource,
) -> ProtocolTranscript:
    return ProtocolTranscript(
        random_source=random_source.name,
        control_coordinates=PublicAnnouncement(
            "coordinates of control modes", route.control_indices
        ),
        control_parameter_coordinates=PublicAnnouncement(
            "s and alpha values of control-mode coordinates", route.control_indices
        ),
        decoy_coordinates=PublicAnnouncement(
            "coordinates of decoy states", route.decoy_indices
        ),
    )
