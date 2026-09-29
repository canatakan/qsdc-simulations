from qsdc.common.random.base import RandomSource
from qsdc.common.random.classical import ClassicalRandomSource
from qsdc.common.random.sf_beamsplitter import SFBeamSplitterQRNG


def make_random_source(name: str, seed: int) -> RandomSource:
    return {"classical": ClassicalRandomSource, "sf-bs-qrng": SFBeamSplitterQRNG}[name](
        seed
    )
