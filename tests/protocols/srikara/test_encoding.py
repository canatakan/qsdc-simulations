from itertools import product

import pytest

from qsdc.common.random import ClassicalRandomSource
from qsdc.protocols.srikara.constants import INTERVAL_CODES
from qsdc.protocols.srikara.simulator.blocks import Block

PAYLOAD = "101001110010011010001101"


@pytest.mark.parametrize("intervals", INTERVAL_CODES)
def test_every_symbol_decodes_from_its_sampled_message_value(intervals):
    code, rng = INTERVAL_CODES[intervals], ClassicalRandomSource(1)
    for bits in code.labels:
        for _ in range(20):
            assert code.decode(code.sample(bits, rng)) == bits


def test_gaussian_intervals_spend_the_default_energy():
    rng = ClassicalRandomSource(2)
    energy = {}
    for name in ("default", "gaussian_gray"):
        code = INTERVAL_CODES[name]
        values = [code.sample(bits, rng) for bits in code.labels for _ in range(2000)]
        energy[name] = sum(v * v for v in values) / len(values)

    assert energy["default"] == pytest.approx(16 / 3, rel=0.03)
    assert energy["gaussian_gray"] == pytest.approx(16 / 3, rel=0.05)


@pytest.mark.parametrize("error_correction", ["none", "parity", "secded"])
@pytest.mark.parametrize("length", [1, 11, 12, 13, 24])
def test_blocks_round_trip_any_payload_length(error_correction, length):
    payload = PAYLOAD[:length]
    blocks = Block.encode(payload, error_correction)
    decoded = [block.decode(block.symbols, error_correction) for block in blocks]

    assert "".join(decoded) == payload


def test_alternating_parity_sends_every_symbol():
    blocks = Block.encode("0000010110101111", "parity")

    assert sorted(block.symbols[0] for block in blocks) == [
        "".join(bits) for bits in product("01", repeat=3)
    ]


def test_secded_block_survives_one_corrupted_symbol_and_detects_two():
    block = Block.encode(PAYLOAD[:12], "secded")[0]
    corrupted = list(block.symbols)

    corrupted[4] = "".join("1" if bit == "0" else "0" for bit in corrupted[4])
    assert block.decode(corrupted, "secded") == block.bits

    corrupted[5] = "".join("1" if bit == "0" else "0" for bit in corrupted[5])
    assert block.decode(corrupted, "secded") is None
