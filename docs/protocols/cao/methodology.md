# Cao Gaussian-Mapping Methodology

## Sources

- Z. Cao et al., "Continuous-Variable Quantum Secure Direct
  Communication Based on Gaussian Mapping," *Physical Review Applied* 16,
  024012 (2021), especially Sec. II and Figs. 1-3.
- Z. Cao et al., "Realization of Quantum Secure Direct Communication with
  Continuous Variable," *Research* 6, 0193 (2023), especially the protocol
  appendix and the parameter-estimation discussion.

The implementation follows the seven stages common to both papers:
correlated-beam preparation, channel detection, authentication, Gaussian
mapping, Gaussian modulation, joint measurement, and postprocessing.

## Paper-to-code mapping

| Paper operation | Implementation |
| --- | --- |
| Two orthogonally squeezed vacua mixed on a 50:50 beam splitter (2021 Eqs. 1-4) | `AnalyticBackend.prepare_correlated_beams` |
| EPR combinations used for the inseparability test (2021 Eq. 5) | `AnalyticBackend.correlation_noise` and protocol security checks |
| Message Gaussian sequence on X and independent parameter-estimation sequence on P | `sample_gaussian_from_interval`, `sample_gaussian`, and `AnalyticBackend.modulate` |
| Joint measurement (2021 Eq. 6) | `AnalyticBackend.measure_message` |
| Alternating message code conversion | `uniformize_message_bits` |
| Random block code conversion | `uniformize_block_bits` |
| Random detection-bit insertion and fixed odd-parity bit | `encode_box` / `decode_box` |
| Equiprobable Gaussian intervals | `gaussian_encoding` and `sample_gaussian_from_interval` |
| Inverse mapping and message extraction | `decode_box`, `restore_block_bits`, `restore_message_bits`, and `simulate_mapping` |

For the paper's worked example, a two-bit block-uniformized payload receives
one random detection bit. Its three mapping bits select one of eight
equiprobable intervals. The appended odd-parity bit is checked separately and
does not change the interval, matching the explanation under Fig. 3.

## Model boundary and assumptions

- The analytic backend is an ideal quadrature model. It implements the 2021
  paper's sign convention, including `P1 + P2` in the joint measurement. The
  2023 realization paper prints a different momentum sign in its appendix;
  adopting it would require changing the beam convention consistently.
- The simulator estimates the inseparability quantity by the sample mean of
  `delta_x**2 + delta_p**2` and compares it with the configurable threshold
  (default 2). It does not separately model the paper's per-location error
  rate.
- Mapping is still evaluated when a security stage is rejected so callers can
  inspect a complete diagnostic result; `accepted` records whether the paper's
  continue/terminate condition was met.
- "Alternately selected" is interpreted as cycling independently through the
  two codewords for each source-bit value. Block uniformization and detection
  bits remain seeded random operations, as stated by the paper.
- The paper calls the appended odd-parity bit an error-correction code. A
  single parity bit detects an odd number of bit flips but cannot locate or
  correct them, so the simulator reports parity validity and does not claim
  correction.
- The odd-parity bit is validated but deliberately excluded from
  `box_bit_length` and Gaussian-interval selection. Only the payload plus
  detection bits select an interval, exactly as described below Fig. 3.
- Detection-bit positions and values are retained as protocol metadata needed
  to validate and remove them during inverse mapping. Authentication of this
  metadata is outside the ideal simulator.
- Interval boundaries use lower-inclusive, upper-exclusive comparisons. The
  papers display the opposite convention at some printed boundaries; this has
  zero probability for continuous sampling and makes adjacent intervals
  unambiguous in software.
- The implementation samples Gaussian values directly with inverse-CDF
  sampling instead of materializing a finite source sequence `G1`. This gives
  the same conditional distribution for each selected interval.
- Parameter estimation, reverse reconciliation, privacy amplification,
  finite-size secrecy-capacity analysis, grading of channel blocks, optical
  loss, detector imperfections, and adversarial channels remain out of scope.
  The P-quadrature random value is modeled but not yet used to estimate a
  channel.
- A non-ideal or adversarial backend can recover a byte sequence that is not
  valid in the configured text encoding. In that case `recovered_message` is
  `None`, `decoding_error` carries the codec error, and `round_trip_ok` is
  false; the simulator does not raise and lose the diagnostic box data.

## Configuration

`box_bit_length` is the number of bits used to select a Gaussian interval.
`detection_bit_count` is the number of those bits reserved for detection, and
their difference is the block-uniformized payload width. The defaults 3 and 1
reproduce the eight-interval example in Fig. 3. The detection count must be
smaller than the box width.

## Verification target

The ideal round trip requires all of the following:

1. measured-and-denoised X values map back to their original interval bits;
2. announced detection bits and odd parity validate for every box;
3. both uniformization transforms invert to the original byte-aligned bits;
4. those bytes decode to the original message using the configured encoding.
