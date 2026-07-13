from dataclasses import dataclass
from math import inf, sqrt
from statistics import NormalDist


@dataclass(frozen=True)
class EncodingInterval:
    """A real-line interval assigned to a 3-bit symbol."""

    bits: str
    lower: float
    upper: float

    def contains(self, value: float) -> bool:
        return self.lower <= value < self.upper


@dataclass(frozen=True)
class GaussianEncoding:
    intervals: tuple[EncodingInterval, ...]
    tail_width: float


def get_gaussian_encoding(bits: list[str], variance: float, mean: float = 0.0) -> GaussianEncoding:
    return GaussianEncoding(
        intervals=_gaussian_intervals_for_bits(bits, variance=variance, mean=mean),
        tail_width=_gaussian_tail_width(variance=variance),
    )


def _gaussian_intervals_for_bits(
    bits: list[str],
    variance: float,
    mean: float = 0.0,
) -> tuple[EncodingInterval, ...]:
    """Return one equiprobable Gaussian interval per bit label.

    The return value is a tuple of ``EncodingInterval`` objects ordered exactly
    like ``bits``. For eight bit labels, the bounds are ``(-inf, q1)``,
    ``(q1, q2)``, ..., ``(q7, inf)``.
    """

    count = len(bits)

    gaussian = NormalDist(
        mu=mean,
        sigma=sqrt(variance),
    )

    # The inner boundaries are inverse-CDF quantiles at 1/count, 2/count, ...
    # so each neighboring pair has probability mass 1/count.
    boundaries = (
        -inf,
        *(gaussian.inv_cdf(i / count) for i in range(1, count)),
        inf,
    )

    return tuple(
        EncodingInterval(
            bits=bits[i],
            lower=boundaries[i],
            upper=boundaries[i + 1],
        )
        for i in range(count)
    )


def _gaussian_tail_width(
    variance: float,
    reference_variance: float = 8.0,
    reference_tail_width: float = 3.75,
) -> float:
    # The reference width 3.75 comes from the finite outer interval
    # [3.25, 7.0] used in the Gaussian-mapping CV-QSDC literature for
    # the variance-8, 8-bin example: 7.0 - 3.25 = 3.75.
    #
    # For other variances, scale the width by the ratio of Gaussian
    # standard deviations. Since sigma = sqrt(variance), preserving the
    # same normalized width w / sigma gives:
    #
    #     w(V) = w_ref * sqrt(V / V_ref)
    #
    # This scaling is a modeling assumption that preserves the same
    # geometry in standard-deviation units; it is not itself prescribed
    # by the cited papers.
    #
    # Sources:
    # - Cao et al., Phys. Rev. Applied 16, 024012 (2021):
    #   Gaussian mapping is analyzed for an original Gaussian sequence
    #   with variance 8 and extended to other variances.
    # - Cao et al., arXiv:2406.11322 (2024):
    #   explicitly uses the finite intervals [-7, -3.25], ..., [3.25, 7].
    return reference_tail_width * sqrt(
        variance / reference_variance
    )
