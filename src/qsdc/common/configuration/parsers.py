from __future__ import annotations

from collections.abc import Sequence


class Parsers:
    @staticmethod
    def probability_sequence(value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            return value
        return [float(item) for item in value]

    @staticmethod
    def serializable_value(value: object) -> object:
        if hasattr(value, "to_dict") and callable(value.to_dict):
            return value.to_dict()
        if isinstance(value, list):
            return [Parsers.serializable_value(item) for item in value]
        if isinstance(value, tuple):
            return [Parsers.serializable_value(item) for item in value]
        if isinstance(value, dict):
            return {
                key: Parsers.serializable_value(item)
                for key, item in value.items()
            }
        return value
