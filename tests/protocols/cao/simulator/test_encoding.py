from qsdc.common.bits import bytes_to_bits, chunk_bits
from qsdc.common.random.classical import ClassicalRandomSource
from qsdc.protocols.cao.simulator.encoding import (
    decode_box,
    encode_box,
    restore_block_bits,
    restore_message_bits,
    uniformize_block_bits,
    uniformize_message_bits,
)


def test_bytes_to_bits():
    assert bytes_to_bits(b"A") == "01000001"


def test_chunk_bits_pads_to_width():
    assert chunk_bits("10101", 3) == ("101", "010")


def test_uniformization_outputs_allowed_codewords():
    random_source = ClassicalRandomSource(3)

    message_uniformized = uniformize_message_bits("00111")
    assert message_uniformized == "0110001100"
    assert restore_message_bits(message_uniformized) == "00111"

    block_uniformized = uniformize_block_bits("01", random_source)
    assert block_uniformized[:2] in {"00", "01"}
    assert block_uniformized[2:] in {"10", "11"}
    assert restore_block_bits(block_uniformized) == "01"


def test_box_encoding_inserts_detection_bits_and_odd_parity():
    box = encode_box(
        payload_bits="01",
        detection_bit_count=1,
        random_source=ClassicalRandomSource(4),
    )

    assert len(box.mapping_bits) == 3
    assert len(box.detection_positions) == 1
    assert (box.codeword.count("1") % 2) == 1

    decoded = decode_box(
        box.mapping_bits,
        box.detection_positions,
        box.detection_bits,
        box.parity_bit,
    )
    assert decoded.payload_bits == "01"
    assert decoded.valid


def test_box_decoding_detects_changed_detection_and_parity_bits():
    box = encode_box(
        payload_bits="10",
        detection_bit_count=1,
        random_source=ClassicalRandomSource(9),
    )
    position = box.detection_positions[0]
    changed_detection = list(box.mapping_bits)
    changed_detection[position] = (
        "1" if changed_detection[position] == "0" else "0"
    )

    decoded = decode_box(
        "".join(changed_detection),
        box.detection_positions,
        box.detection_bits,
        box.parity_bit,
    )

    assert not decoded.detection_valid
    assert not decoded.parity_valid

    parity_tampered = decode_box(
        box.mapping_bits,
        box.detection_positions,
        box.detection_bits,
        1 - box.parity_bit,
    )
    assert parity_tampered.detection_valid
    assert not parity_tampered.parity_valid
