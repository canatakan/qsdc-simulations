import pytest

from qsdc.protocols.srikara.simulator.backends import AnalyticBackend


class Eavesdropper(AnalyticBackend):
    def measure_returned(self, state, axis, beta=0j):
        return super().measure_returned(state, axis, beta) + 0.5


class CorruptFirstMessage(AnalyticBackend):
    def begin_run(self, seed):
        self.corrupted = False

    def measure_returned(self, state, axis, beta=0j):
        value = super().measure_returned(state, axis, beta)
        if beta and not self.corrupted:
            self.corrupted = True
            value += (3.0 if beta.real < 0 else -3.0) * self.message_response(
                state, axis
            )
        return value


class RejectEveryOtherRun(AnalyticBackend):
    runs = 0

    def begin_run(self, seed):
        self.runs += 1

    def measure_control(self, state, axis):
        return super().measure_control(state, axis) + self.runs % 2


@pytest.fixture
def eavesdropper():
    return Eavesdropper


@pytest.fixture
def corrupt_first_message():
    return CorruptFirstMessage


@pytest.fixture
def reject_every_other_run():
    return RejectEveryOtherRun
