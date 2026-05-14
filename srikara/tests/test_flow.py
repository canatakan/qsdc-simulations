from simulator.core.flow import ModeRoute, OpticalSwitch, build_transcript
from simulator.core.random_source import ClassicalRandomSource


def test_optical_switch_partitions_modes():
    route = OpticalSwitch(ClassicalRandomSource(3)).route(12)

    assert len(route.control_indices) == 6
    assert len(route.delayed_indices) == 6
    assert len(route.message_indices) == 3
    assert len(route.decoy_indices) == 3

    assert set(route.control_indices).isdisjoint(route.delayed_indices)
    assert set(route.message_indices).isdisjoint(route.decoy_indices)
    assert set(route.message_indices) | set(route.decoy_indices) == set(
        route.delayed_indices
    )
    assert set(route.control_indices) | set(route.delayed_indices) == set(range(12))


def test_transcript_records_public_announcement_labels_and_indices():
    route = ModeRoute(
        control_indices=(0, 2),
        delayed_indices=(1, 3),
        message_indices=(1,),
        decoy_indices=(3,),
    )

    transcript = build_transcript(route, ClassicalRandomSource(1))

    assert transcript.random_source == "classical"
    assert transcript.control_coordinates.label == "coordinates of control modes"
    assert transcript.control_coordinates.indices == (0, 2)
    assert (
        transcript.control_parameter_coordinates.label
        == "s and alpha values of control-mode coordinates"
    )
    assert transcript.control_parameter_coordinates.indices == (0, 2)
    assert transcript.decoy_coordinates.label == "coordinates of decoy states"
    assert transcript.decoy_coordinates.indices == (3,)
