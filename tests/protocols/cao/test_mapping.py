from math import sqrt
from statistics import fmean, pvariance

import pytest

from qsdc.common.random import ClassicalRandomSource, RandomSource, weighted_random_bits
from qsdc.protocols.cao.config import SimulatorConfig
from qsdc.protocols.cao.simulator.mapping import (
    interval_code,
    map_box,
    restore_block,
    restore_message,
    uniformize_block,
    uniformize_message,
)
from qsdc.protocols.cao.simulator.protocol import encode_blocks


class ScriptedRandom(RandomSource):
    name = "scripted"

    def __init__(self, draws):
        self.draws = iter(draws)

    def uniform(self, lower, upper):
        raise AssertionError("not scripted")

    def randbelow(self, n):
        draw = next(self.draws)
        assert draw < n
        return draw


def test_reproduces_the_worked_example_of_figure_3():
    assert uniformize_message("10") == "0001"
    rng = ScriptedRandom([1, 1, 0, 0])
    assert uniformize_block("0001", rng) == "01010010"

    rng = ScriptedRandom([0, 1, 0, 2, 1, 1, 0, 1, 0, 0, 1, 0])
    boxes = [map_box(payload, 1, rng) for payload in ("01", "01", "00", "10")]

    assert [box.bits + box.parity for box in boxes] == ["0100", "1011", "0001", "1000"]
    assert [box.unmap(box.bits) for box in boxes] == ["01", "01", "00", "10"]


def test_reproduces_the_intervals_of_table_1():
    code = interval_code(SimulatorConfig())

    assert code.labels == ("000", "001", "010", "011", "100", "101", "110", "111")
    assert [round(bound, 4) for bound in code.bounds[1:-1]] == [
        -3.2537,
        -1.9077,
        -0.9012,
        0.0,
        0.9012,
        1.9077,
        3.2537,
    ]


@pytest.mark.parametrize("one_probability", [0.1, 0.5, 0.9])
def test_uniformizations_invert(one_probability):
    rng = ClassicalRandomSource(5)
    bits = weighted_random_bits(500, one_probability, rng)

    message = uniformize_message(bits)
    block = uniformize_block(message, rng)

    assert restore_block(block) == message
    assert restore_message(message) == bits


def test_message_uniformization_balances_a_biased_payload():
    bits = "1" * 90 + "0" * 10

    assert uniformize_message(bits).count("1") == 100


def test_boxes_carry_detection_and_odd_parity_bits():
    rng = ClassicalRandomSource(2)
    for payload in ("00", "01", "10", "11"):
        box = map_box(payload, 2, rng)

        assert len(box.bits) == 4 and len(box.detection) == 2
        assert box.unmap(box.bits) == payload
        assert (box.bits + box.parity).count("1") % 2 == 1
        assert box.detection_matches(box.bits) and box.parity_matches(box.bits)


def test_a_wrong_bit_fails_parity():
    box = map_box("01", 1, ClassicalRandomSource(4))
    flipped = "".join("1" if bit == "0" else "0" for bit in box.bits[:1]) + box.bits[1:]

    assert not box.parity_matches(flipped)


def test_mapping_keeps_the_gaussian_of_a_biased_payload():
    config = SimulatorConfig()
    code = interval_code(config)
    rng = ClassicalRandomSource(8)
    payload = weighted_random_bits(4000, 0.9, rng)
    values = []
    for block in encode_blocks(payload, config.block_bits):
        bits = uniformize_block(block.uniformized, rng)
        for i in range(0, len(bits), config.box_bits):
            box = map_box(bits[i : i + config.box_bits], config.detection_bits, rng)
            values.append(code.sample(box.bits, rng))

    assert abs(fmean(values)) < 0.05 * sqrt(config.modulation_variance_snu)
    assert pvariance(values) == pytest.approx(config.modulation_variance_snu, rel=0.05)


def test_blocks_split_the_payload_and_its_uniformization():
    blocks = encode_blocks("10011", 2)

    assert [block.bits for block in blocks] == ["10", "01", "1"]
    assert "".join(block.uniformized for block in blocks) == uniformize_message(
        "100110"
    )
