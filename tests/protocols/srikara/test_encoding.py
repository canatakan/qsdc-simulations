import pytest

from qsdc.common.random.classical import ClassicalRandomSource
from qsdc.protocols.srikara.simulator.backends import AnalyticBackend
from qsdc.protocols.srikara.simulator.encoding import INTERVAL_CODES
from qsdc.protocols.srikara.simulator.transport import decode_block, encode_blocks

PAYLOAD = "101001110010011010001101"


@pytest.mark.parametrize("intervals", INTERVAL_CODES)
def test_every_symbol_decodes_from_its_sampled_message_value(intervals):
    code, rng = INTERVAL_CODES[intervals], ClassicalRandomSource(1)
    for bits in code.labels:
        for _ in range(20):
            assert code.decode(code.sample(bits, rng)) == bits


def test_equal_energy_code_spends_the_default_energy():
    assert INTERVAL_CODES["optimized_equal_energy"].energy_snu == pytest.approx(
        INTERVAL_CODES["default"].energy_snu
    )
    assert INTERVAL_CODES["default"].energy_snu == pytest.approx(64 / 3)


def test_unsqueezing_inverts_the_squeeze_displacement_relation():
    beta = AnalyticBackend.squeezed_displacement(0.7 - 1.2j, 0.43, 0.9)
    assert AnalyticBackend.unsqueezed_displacement(beta, 0.43, 0.9) == pytest.approx(
        0.7 - 1.2j
    )


@pytest.mark.parametrize("error_correction", ["none", "parity", "secded"])
@pytest.mark.parametrize("length", [1, 11, 12, 13, 24])
def test_blocks_round_trip_any_payload_length(error_correction, length):
    payload = PAYLOAD[:length]
    blocks = encode_blocks(payload, error_correction)
    decoded = [decode_block(block, block.symbols, error_correction) for block in blocks]

    assert "".join(decoded) == payload


def test_secded_block_survives_one_corrupted_symbol_and_detects_two():
    block = encode_blocks(PAYLOAD[:12], "secded")[0]
    corrupted = list(block.symbols)
    corrupted[4] = "".join("1" if bit == "0" else "0" for bit in corrupted[4])
    assert decode_block(block, corrupted, "secded") == block.bits

    corrupted[5] = "".join("1" if bit == "0" else "0" for bit in corrupted[5])
    assert decode_block(block, corrupted, "secded") is None
