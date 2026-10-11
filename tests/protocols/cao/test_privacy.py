import numpy as np

from qsdc.common.coding.universal_hash import UniversalHash
from qsdc.common.random import derive_seed
from qsdc.protocols.cao.config import SimulatorConfig
from qsdc.protocols.cao.simulator.postprocessing import reconciliation_code


def gf2_rank(rows, length):
    matrix = np.zeros((len(rows), length), dtype=bool)
    for i, row in enumerate(rows):
        matrix[i, list(row)] = True
    rank = 0
    for column in range(length):
        candidates = np.flatnonzero(matrix[rank:, column])
        if candidates.size == 0:
            continue
        pivot = rank + candidates[0]
        matrix[[rank, pivot]] = matrix[[pivot, rank]]
        others = np.flatnonzero(matrix[:, column])
        matrix[others[others != rank]] ^= matrix[rank]
        rank += 1
        if rank == len(rows):
            break
    return rank


def test_public_bits_reveal_nothing_about_the_message():
    # The payload is uniform among the inputs with the message as hash, and
    # every public bit is a parity of the payload. The message stays hidden
    # exactly when no combination of public bits equals a combination of
    # message bits, that is when the hash rows add their full rank.
    config = SimulatorConfig()
    public = reconciliation_code(config).rows
    hashing = UniversalHash(
        config.payload_bits,
        config.block_bits,
        seed=derive_seed(config.seed, "universal hash"),
    )

    public_rank = gf2_rank(public, config.payload_bits)
    combined_rank = gf2_rank([*public, *hashing.rows()], config.payload_bits)

    assert len(public) == config.public_bits
    assert combined_rank == public_rank + config.block_bits


def test_message_bits_follow_the_public_bits():
    config = SimulatorConfig()

    assert config.block_bits == (
        config.payload_bits
        - config.boxes
        - config.syndrome_bits
        - config.reconciliation.secrecy_margin
    )
