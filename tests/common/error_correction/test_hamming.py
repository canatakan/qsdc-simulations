from itertools import combinations, product

from qsdc.common.error_correction import Secded84

CODEC = Secded84()
DATA_WORDS = tuple("".join(bits) for bits in product("01", repeat=4))


def _flip(word, *positions):
    result = list(word)
    for position in positions:
        result[position] = "1" if result[position] == "0" else "0"
    return "".join(result)


def test_all_data_words_round_trip_and_use_systematic_positions():
    for data_bits in DATA_WORDS:
        encoded = CODEC.encode(data_bits)

        assert "".join(encoded[index] for index in (2, 4, 5, 6)) == data_bits
        result = CODEC.decode(encoded)

        assert result.status == "clean"
        assert result.data_bits == data_bits
        assert result.corrected_bits == 0


def test_every_single_bit_error_is_corrected():
    for data_bits in DATA_WORDS:
        encoded = CODEC.encode(data_bits)
        for position in range(8):
            result = CODEC.decode(_flip(encoded, position))

            assert result.status == "corrected"
            assert result.data_bits == data_bits
            assert result.corrected_bits == 1


def test_every_double_bit_error_is_detected():
    for data_bits in DATA_WORDS:
        encoded = CODEC.encode(data_bits)
        for positions in combinations(range(8), 2):
            result = CODEC.decode(_flip(encoded, *positions))

            assert result.status == "uncorrectable"
            assert result.data_bits is None


def test_up_to_three_clean_erasures_are_recovered():
    for data_bits in DATA_WORDS:
        encoded = CODEC.encode(data_bits)
        for erasure_count in range(1, 4):
            for positions in combinations(range(8), erasure_count):
                received = encoded
                for position in positions:
                    received = received[:position] + "?" + received[position + 1 :]

                result = CODEC.decode(received)

                assert result.status == "corrected"
                assert result.data_bits == data_bits
                assert result.recovered_erasures == erasure_count
                assert result.corrected_bits == 0


def test_one_erasure_plus_one_observed_error_is_recovered():
    for data_bits in DATA_WORDS:
        encoded = CODEC.encode(data_bits)
        for erased in range(8):
            for erroneous in range(8):
                if erased == erroneous:
                    continue
                received = _flip(encoded, erroneous)
                received = received[:erased] + "?" + received[erased + 1 :]

                result = CODEC.decode(received)

                assert result.status == "corrected"
                assert result.data_bits == data_bits
                assert result.recovered_erasures == 1
                assert result.corrected_bits == 1


def test_four_erasures_are_not_bounded_distance_decodable():
    received = CODEC.encode("1010")
    for position in (0, 1, 2, 3):
        received = received[:position] + "?" + received[position + 1 :]

    result = CODEC.decode(received)

    assert result.status == "uncorrectable"
    assert result.data_bits is None


def test_three_errors_can_miscorrect_and_are_not_claimed_as_guaranteed():
    encoded = CODEC.encode("0000")

    result = CODEC.decode(_flip(encoded, 0, 1, 2))

    assert result.status == "corrected"
    assert result.data_bits == "1000"
    assert result.data_bits != "0000"
