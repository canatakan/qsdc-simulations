from qsdc.protocols.cao.simulator.config import MappingConfig
from qsdc.protocols.cao.simulator.protocol import simulate_mapping


def test_mapping_protocol_round_trips_boxes():
    result = simulate_mapping(
        "A",
        config=MappingConfig(seed=7, gaussian_variance=4.0, box_bit_length=3),
    )

    assert result.backend_name == "analytic"
    assert result.random_source_name == "classical"
    assert result.raw_bits == "01000001"
    assert result.round_trip_ok
    assert all(box.bits == box.recovered_bits for box in result.boxes)
