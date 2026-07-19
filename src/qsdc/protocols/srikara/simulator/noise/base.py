"""Contracts for executable optical and classical noise effects."""

from __future__ import annotations

from abc import ABC, abstractmethod


class OpticalEffect(ABC):
    """An effect that inserts its own operation into an SF circuit."""

    @abstractmethod
    def apply(self, register: object) -> object:
        """Apply this optical effect and return the same circuit register."""


class ChannelEffect(OpticalEffect):
    """An optical effect located on a transmission path."""

    @property
    @abstractmethod
    def amplitude_gain(self) -> float:
        """Return this effect's field-amplitude gain for a displacement."""


class DetectorEffect(OpticalEffect):
    """An optical effect located immediately before measurement."""

    @property
    @abstractmethod
    def amplitude_gain(self) -> float:
        """Return this effect's field-amplitude gain for a displacement."""


class ReadoutEffect(ABC):
    """A classical effect applied after the one optical measurement."""

    @abstractmethod
    def apply(self, measured: float) -> float:
        """Transform one already measured classical value."""
