from dataclasses import replace

from qsdc.protocols.cao.simulator.backends.analytic.ideal import AnalyticBackend
from qsdc.protocols.cao.simulator.config import MappingConfig
from qsdc.protocols.cao.simulator.protocol import simulate_mapping


def test_mapping_protocol_round_trips_boxes():
    result = simulate_mapping(
        "A",
        config=MappingConfig.from_options(
            seed=7,
            gaussian_variance=4.0,
            box_bit_length=3,
        ),
    )

    assert result.backend_name == "analytic"
    assert result.random_source_name == "classical"
    assert result.raw_bits == "01000001"
    assert result.recovered_raw_bits == result.raw_bits
    assert result.recovered_message == "A"
    assert result.round_trip_ok
    assert all(
        box.bits == box.recovered_bits
        and box.detection_valid
        and box.parity_valid
        for box in result.boxes
    )


def test_mapping_protocol_removes_partial_box_padding():
    result = simulate_mapping(
        "A",
        config=MappingConfig.from_options(
            seed=7,
            box_bit_length=4,
            detection_bit_count=1,
        ),
    )

    assert len(result.block_uniformized_bits) % 3 == 2
    assert result.recovered_block_uniformized_bits == result.block_uniformized_bits
    assert result.recovered_message == "A"
    assert result.round_trip_ok


class CorruptingBackend(AnalyticBackend):
    name = "corrupting"

    def measure_message(self, beam):
        measured = super().measure_message(beam)
        return replace(measured, x_message=100.0)


def test_mapping_protocol_reports_invalid_recovered_text_without_raising():
    result = simulate_mapping(
        "A",
        config=MappingConfig.from_options(seed=7),
        backend=CorruptingBackend(),
    )

    assert result.recovered_message is None
    assert result.decoding_error is not None
    assert not result.round_trip_ok
