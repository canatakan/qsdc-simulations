from qsdc.common.bits import bytes_to_bits, chunk_bits
from qsdc.common.random.classical import ClassicalRandomSource
from qsdc.protocols.cao.simulator.encoding import (
    uniformize_block_bits,
    uniformize_message_bits,
)


def test_bytes_to_bits():
    assert bytes_to_bits(b"A") == "01000001"


def test_chunk_bits_pads_to_width():
    assert chunk_bits("10101", 3) == ("101", "010")


def test_uniformization_outputs_allowed_codewords():
    random_source = ClassicalRandomSource(3)

    message_uniformized = uniformize_message_bits("01", random_source)
    assert message_uniformized[:2] in {"01", "10"}
    assert message_uniformized[2:] in {"00", "11"}

    block_uniformized = uniformize_block_bits("01", random_source)
    assert block_uniformized[:2] in {"00", "01"}
    assert block_uniformized[2:] in {"10", "11"}
