from __future__ import annotations

from collections.abc import Sequence


class Validators:
    @staticmethod
    def string(value: object) -> bool:
        return isinstance(value, str)

    @staticmethod
    def nonempty_string(value: object) -> bool:
        return isinstance(value, str) and bool(value)

    @staticmethod
    def optional_string(value: object) -> bool:
        return value is None or isinstance(value, str)

    @staticmethod
    def bool(value: object) -> bool:
        return isinstance(value, bool)

    @staticmethod
    def string_sequence(value: object) -> bool:
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            return False
        return bool(value) and all(isinstance(item, str) for item in value)

    @staticmethod
    def int(value: object) -> bool:
        return isinstance(value, int) and not isinstance(value, bool)

    @staticmethod
    def positive_int(value: object) -> bool:
        return Validators.int(value) and value > 0

    @staticmethod
    def nonnegative_int(value: object) -> bool:
        return Validators.int(value) and value >= 0

    @staticmethod
    def number(value: object) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    @staticmethod
    def positive_number(value: object) -> bool:
        return Validators.number(value) and value > 0.0

    @staticmethod
    def nonnegative_number(value: object) -> bool:
        return Validators.number(value) and value >= 0.0

    @staticmethod
    def probability(value: object) -> bool:
        return Validators.number(value) and 0.0 <= value <= 1.0

    @staticmethod
    def probability_sequence(value: object) -> bool:
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            return False
        return bool(value) and all(Validators.probability(item) for item in value)
