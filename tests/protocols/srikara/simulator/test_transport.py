import pytest

from qsdc.protocols.srikara.simulator.transport import decode_block, encode_payload


@pytest.mark.parametrize("length", [1, 3, 4, 11, 12, 13, 23, 24, 32])
def test_secded_transport_round_trips_boundary_lengths(length):
    payload = ("10110010" * ((length + 7) // 8))[:length]
    frame = encode_payload(payload, "secded")
    decoded = [decode_block(block, block.symbols, "secded") for block in frame.blocks]

    assert "".join(result.recovered_bits for result in decoded) == payload
    assert frame.padding_bit_count == (-length) % 12
    assert frame.transmitted_bit_count == 24 * len(frame.blocks)
    assert frame.symbol_count == 8 * len(frame.blocks)
    assert frame.first_attempt_state_count == 32 * len(frame.blocks)


def test_interleaving_is_column_major_across_three_codewords():
    block = encode_payload("000100100100", "secded").blocks[0]
    encoded = block.encoded_bits
    codewords = tuple(encoded[lane::3] for lane in range(3))

    assert block.symbols == tuple(
        "".join(codeword[index] for codeword in codewords) for index in range(8)
    )


def test_one_bad_symbol_is_corrected_in_every_lane():
    block = encode_payload("101001110010", "secded").blocks[0]
    received = list(block.symbols)
    received[4] = "".join("1" if bit == "0" else "0" for bit in received[4])

    decoded = decode_block(block, received, "secded")

    assert decoded.recovered_bits == "101001110010"
    assert decoded.corrected_codewords == 3
    assert decoded.corrected_bits == 3


@pytest.mark.parametrize("erasure_count", [1, 2, 3])
def test_up_to_three_erased_symbols_are_recovered(erasure_count):
    block = encode_payload("101001110010", "secded").blocks[0]
    received = list(block.symbols)
    for index in range(erasure_count):
        received[index] = None

    decoded = decode_block(block, received, "secded")

    assert decoded.recovered_bits == "101001110010"
    assert decoded.recovered_erasures == 3 * erasure_count


def test_four_erased_symbols_are_uncorrectable():
    block = encode_payload("101001110010", "secded").blocks[0]
    decoded = decode_block(block, (None,) * 4 + block.symbols[4:], "secded")

    assert decoded.recovered_bits is None
    assert decoded.uncorrectable_codewords == 3
