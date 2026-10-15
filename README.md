# QSDC Simulations

Simulators for quantum secure direct communication (QSDC) protocols, one
package per paper: [`srikara`](#srikara-protocol) and [`cao`](#cao-protocol).
The [benchmark](#benchmarks) package runs their simulators in studies and
writes reports, and the [demo](#demo) package walks through one transmission.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
make install
```

`make install` adds three commands to `.venv/bin`: `benchmark`, `srikara-demo`
and `cao-demo`. `benchmark` takes `srikara` or `cao` as its first argument.
To run the tests, use `make test`.

## Layout

| Path | Contents |
| --- | --- |
| `src/qsdc/common/config/` | Configuration base classes, value types, noise models and the noise baselines |
| `src/qsdc/common/coding/` | Bits, interval codes, parity, SECDED, LDPC and the universal hash |
| `src/qsdc/common/` | Quadratures, random sources, block transmission with retries |
| `src/qsdc/protocols/<protocol>/simulator/` | The protocol's simulator and its backends |
| `src/qsdc/protocols/<protocol>/config.py`, `constants.py` | Its settings, noise configurations, fixed values and unit conventions |
| `src/qsdc/protocols/<protocol>/presets.yaml` | Its named simulator configurations |
| `src/qsdc/benchmark/` | The benchmark runner, metrics, the `Suite` base class and the command line |
| `src/qsdc/benchmark/studies/` | The catalog that builds studies from `studies.yaml` |
| `src/qsdc/benchmark/studies/<protocol>/` | A protocol's suite and its studies |
| `src/qsdc/benchmark/report/` | Reports: results, CSV, plots, and the HTML templates and stylesheet |
| `src/qsdc/benchmark/results/<protocol>/` | The benchmark results of each protocol (not tracked by git) |
| `src/qsdc/demo/<protocol>.py` | A protocol's demo |
| `src/qsdc/demo/console.py` | The demos' headers and tables |
| `tests/` | Tests, laid out like `src/` |

The protocols import neither the benchmark nor the demos. A suite in
`benchmark/studies/<protocol>/` runs the protocol's simulator and measures its
transmissions.

## Srikara protocol

> S. Srikara, K. Thapliyal, and A. Pathak, Continuous variable direct secure
> quantum communication using gaussian states, Quantum Inf. Process. 19, 1 (2020).

Alice sends a message to Bob over two optical passes. Each 3-bit symbol uses
4 squeezed coherent states:

1. Bob prepares the states with random α, r and θ and sends them to Alice.
2. Alice checks half of them (the controls) against the values Bob reveals.
   If too many of them fail, the attempt aborts here.
3. Alice displaces a quarter (the messages) by m(1 + i), where the interval of
   m encodes 3 bits. She leaves the last quarter (the decoys) unchanged and
   sends both back.
4. Bob unsqueezes and measures the returned states, checks the decoys, and
   decodes m from the messages.

The message is sent in attempts. An attempt prepares the states of every block
not yet released at once, and Alice picks the controls, messages and decoys
among all of them. A check passes when it falls within k = `tolerance_sigmas`
of its expected value, which an honest check misses with probability
q = erfc(k/√2). The controls of an attempt form one security test, and its
decoys another. A test passes when at most q + k · √(q(1 − q)/n) of its n
checks fail. A failed test aborts the whole attempt, as in the paper, where
Alice "discards the protocol, and they start all over again".

### Usage

```python
from qsdc.protocols.srikara.config import SimulatorConfig
from qsdc.protocols.srikara.simulator.protocol import Simulator

config = SimulatorConfig(error_correction="secded", max_attempts=3)
transmission = Simulator(config).transmit("101001110010")
assert transmission.recovered_bits == "101001110010"
```

`SimulatorConfig` (`config.py`) holds every option. Its defaults are the
noiseless paper setting. `recovered_bits` is set only when every block was
released. `PRESETS` and `NOISES` in `config.py` hold the
[simulator presets](#presets) and the [noise baselines](#noise-baselines).

### Backends

| `backend` | Behaviour |
| --- | --- |
| `analytic` | The paper's algebra. Ignores `noise`. |
| `sf` | Strawberry Fields Gaussian circuits with noise, read out as exact means |
| `sf-sampled` | The same circuits, read out as homodyne samples |

The Strawberry Fields backends model `noise` as a thermal loss channel in each
direction, Alice's memory, and each party's detector efficiency and electronic
noise. Checks compare against the expectation of the same noisy circuit. If
no signal reaches Bob, he decodes m = 0.

### Measurement axis

`axis_policy` sets the quadrature Bob measures on a message mode. Control and
decoy checks always measure q or p at random.

| `axis_policy` | Bob measures |
| --- | --- |
| `random` | q or p at random, as in the paper |
| `best_qp` | whichever of q and p responds more to Alice's displacement |
| `aligned` | the quadrature along the unsqueezed displacement, which Bob computes from s |

The squeezing angle sets how much signal Bob reads per unit m:

- `aligned` reads the most at θ = 3π/2: √2·e^r.
- q or p alone read the most at θ = 5π/4 or 7π/4: cosh r + √2 sinh r. That is
  about 15% less than `aligned` at the same angle.
- The signal is weakest at θ = π/2.

### Intervals

| `intervals` | Layout |
| --- | --- |
| `default` | The paper's 8 intervals of m, labelled in binary order |
| `gray` | The same intervals with Gray labels, so neighbouring intervals differ by one bit |
| `gaussian_gray` | Cao et al.'s equiprobable intervals for Gaussian m, with Gray labels |

Cao et al. give their intervals for V_A = 8 SNU and a vacuum standard
deviation of 1. Here the equiprobable intervals are computed for the paper's
mean energy of 64/3 SNU and this simulator's vacuum standard deviation of 1/2.
Only the layout differs from `gray`.

### Error correction and retries

| `error_correction` | Payload bits per block | Symbols per block | States per block | Effect |
| --- | --- | --- | --- | --- |
| `none` | 3 | 1 | 4 | none |
| `parity` | 2 | 1 | 4 | detects an odd number of wrong bits |
| `secded` | 12 | 8 | 32 | corrects one wrong symbol per block |
| `ldpc` | 96 (configurable) | 64 (default) | 256 (default) | soft-decision decoding of transmitted codewords |

- **Parity:** the parity bit is part of the symbol. Blocks alternate between
  odd and even parity, so all 8 intervals are used and m stays zero-mean, as
  Cao et al. require. With Gray labels, an error into a neighbouring interval is
  always detected.
- **SECDED:** the block is three extended Hamming (8, 4) codewords,
  interleaved so each symbol carries one bit of each codeword.
- **LDPC:** a systematic sparse code with a dual-diagonal parity section.
  The default sends 96 data bits plus 96 parity bits, grouped into 3-bit symbols.
  Bob computes bit log-likelihood ratios from the received value and the
  model's readout variance divided by the squared message response. Uniform
  layouts use their finite sampling supports; Gaussian layouts use their
  Gaussian prior. Exact-mean backends use noiseless likelihoods. A block with
  no signal is unrecovered. Decoding targets the all-zero syndrome; no
  message-dependent syndrome is announced on a classical channel.
- **Attempts:** at most `max_attempts` attempts. An aborted attempt sends all
  its blocks again, and a block whose code finds an error it cannot correct
  goes again in the next attempt. Each attempt draws fresh states.
- **Padding:** the last block is padded with zeros. The padding is removed
  after decoding.

Enable LDPC with `SimulatorConfig(error_correction="ldpc")`, or run
`srikara-demo "hello" --simulator ldpc`. To change its shape:

```python
from qsdc.protocols.srikara.config import LdpcConfig, SimulatorConfig

config = SimulatorConfig(
    error_correction="ldpc",
    ldpc=LdpcConfig(data_bits=192, parity_bits=192, column_weight=3,
                    max_iterations=100, seed=0),
)
```

The total codeword length must be divisible by 3. The code seed fixes the
parity-check matrix independently of the channel seed and retry number.
This LDPC construction is a simulation extension, not a code specified by the
Srikara paper. Its soft demapper assumes equally likely labels, and its noise
variance comes from the simulator model rather than channel estimation.
Convergence means parity checks pass; it does not guarantee correct recovery
or establish secrecy. Benchmark error rates still compare the delivered bits
against the original payload.

## Cao protocol

> Z. Cao, L. Wang, K. Liang, G. Chai, and J. Peng, Continuous-variable quantum
> secure direct communication based on Gaussian mapping, Phys. Rev. Appl. 16,
> 024012 (2021).

Alice keeps one half of each two-mode squeezed pair and sends the other to
Bob. A block uses `2 · check_pairs + boxes` pairs:

1. Two squeezed vacua on a 50:50 beam splitter give S1 (Alice) and S2 (Bob).
2. **Channel detection:** both heterodyne x and p on positions Alice picks. A
   position passes when X_m² + P_m² < 2, with X_m = (x_A − x_B)/√2 and
   P_m = (p_A + p_B)/√2, which is Duan's inseparability criterion.
3. **Authentication:** the same test on positions Bob picks.
4. **Gaussian mapping:** the payload is split into boxes of 2 bits, a random
   detection bit is inserted into each, and the box selects one of 8
   equiprobable intervals of N(0, V_A); G1' is drawn inside it. Each box's odd
   parity bit is announced with the detection bits, not mapped.
5. Alice displaces X of S1 by G1' and P by an independent Gaussian G2.
6. Bob measures the arriving beam jointly with S2: X_m = (X_info − X_2)/√2,
   P_m = (P_info + P_2)/√2.
7. **Postprocessing:** parameter estimation, reconciliation and privacy
   amplification (below).

Quadratures are in shot-noise units with a vacuum variance of 1, as in the
paper.

### Usage

```python
from qsdc.protocols.cao.config import SimulatorConfig
from qsdc.protocols.cao.simulator.protocol import Simulator

transmission = Simulator(SimulatorConfig(max_attempts=3)).transmit("1010")
```

`SimulatorConfig` (`config.py`) holds every option. A block has 512 boxes, so
1024 payload bits, which keeps the reconciliation code long enough.

### Backends

| `backend` | Behaviour |
| --- | --- |
| `analytic` | The paper's formulas on mean values: Bob reads Alice's displacement / √2, and every check outcome is 0. Ignores `noise`. |
| `sf` | Strawberry Fields Gaussian circuits with noise, one per check or signal, read out as exact means |
| `sf-sampled` | The same circuits, read out as homodyne samples (default) |

`noise` places a noise baseline on the links of the paper's Fig. 1: S1 waits
in Alice's delay line before she displaces it and sends it through the fibre;
S2 crosses the same fibre and waits in Bob's delay line; each detector adds its
loss and electronic noise. `sf` and `sf-sampled` build it into the circuits.
Strawberry Fields 0.23's `ThermalLossChannel` adds its thermal photons to every
mode of a circuit, so each thermal loss is built from a beam splitter and a
thermal mode.

### Checks

The paper gives no threshold for the checks. The message is sent in attempts.
An attempt prepares the pairs of every block not yet released at once, and each
security test takes `check_pairs` positions per block at random among all of
them, n in all. A test passes when at most
q + `check_tolerance_sigmas` · √(q(1 − q)/n) of them fail, where q = e^(−1/σ²)
is the failure rate of an honest pair. A failed test terminates the whole
attempt. The backend's `check_sigma` gives σ: from the paper's formulas for
`analytic`, and from the covariance of the noisy circuit for `sf` and
`sf-sampled`. An honest
position fails 15% of the time on `clean` and 40% on `record_27km`.

### Postprocessing

| Step | What happens |
| --- | --- |
| Parameter estimation | Alice reveals G2; Bob fits P_m = t G2 + noise for his gain and noise |
| Reconciliation | Alice sends an LDPC syndrome of `syndrome_fraction` × 1024 bits. Bob decodes his payload from X_m / t, using the announced detection bits and one check per announced parity bit |
| Privacy amplification | Bob hashes the corrected payload into the message |

The paper names reverse reconciliation and privacy amplification but specifies
neither. Reverse reconciliation corrects Alice's data towards Bob's, which suits
a random key but not a message, so reconciliation here is direct. Hashing the
reconciled data down would destroy a message, so privacy amplification is
applied in reverse, as in practical QSDC systems: Alice picks her payload
uniformly among all payloads whose universal hash is the message, using fresh
random bits.

Each announced parity bit and each syndrome bit costs one message bit:

```text
block_bits = payload_bits − boxes − syndrome bits − secrecy_margin (32)
```

The tests check that the public bits then reveal nothing about the message.
What Eve could learn on the quantum channel is not counted; the paper's
security analysis (Sec. III) is not implemented.

`SYNDROME_FRACTIONS` (`config.py`) holds the smallest syndrome fraction that
reconciled 12 of 12 blocks on each baseline, and `cao-demo` uses it:

| Baseline | Syndrome fraction | Message bits per block |
| --- | --- | --- |
| `clean` | 0.10 | 378 |
| `lab` | 0.25 | 224 |
| `metro_5km` | 0.40 | 70 |
| `metro_10km`, `record_27km` | none | even 0.45 reconciles almost no block, and above about 0.47 no message bits are left |

An attempt sends every block not yet released, up to `max_attempts` attempts. A
terminated attempt sends all its blocks again, and a block that fails its
reconciliation goes again in the next attempt, with the same payload so a retry
publishes nothing new.
With `reconciliation=None`, the paper's mapping is used instead: the message
is uniformized twice, Bob decodes every box on its own, and a block is released
only when every box passes its detection and parity bits.

### Defaults the paper does not give

| Setting | Value | Reason |
| --- | --- | --- |
| `squeeze_r` | arcosh(9)/2 ≈ 1.444 (12.5 dB) | The two-mode squeezed state then has the variance V = V_A + 1 of the paper's security model |
| `check_pairs` | 64 per block and security test | Enough positions for a stable failure rate |
| `check_tolerance_sigmas` | 3 | As in Srikara |
| `syndrome_fraction` | 0.3 | Enough up to `lab`; `SYNDROME_FRACTIONS` gives each baseline its own |

The modulation is taken literally: Alice displaces by G1' itself, so Bob reads
G1'/√2 on top of the pair's squeezed noise. About a fifth of the boxes are
decoded into a wrong interval on `clean` and two fifths on `lab`;
reconciliation removes these errors.

## Demo

The demos are in `src/qsdc/demo/`. `srikara-demo` sends a text message. It
prints one line per block and attempt, then every protocol step of one block,
with the verdict of each security test over the attempt. It uses the `retry` simulator
under `lab` noise unless told otherwise.

```bash
srikara-demo "hello"
srikara-demo "hello" --simulator baseline --noise clean
srikara-demo "hello" --noise metro_10km --block 3 --trace
```

| Option | Effect |
| --- | --- |
| `--simulator`, `--noise` | A [simulator preset](#presets) and a [noise baseline](#noise-baselines) |
| `--block` | The block to show step by step, counted from 0 (default: the one with the most sends) |
| `--trace` | Adds the noise path of each mode in that block |

`srikara-demo --help` lists every option.

`cao-demo` does the same for Cao. It runs the default configuration on the
`clean` baseline unless told otherwise.

```bash
cao-demo "hello"
cao-demo "hello" --noise lab --rows 12
cao-demo "hello" --noise metro_5km
cao-demo "hello" --noise lab --syndrome-fraction 0.3
```

| Option | Effect |
| --- | --- |
| `--noise` | A noise baseline |
| `--syndrome-fraction` | Syndrome bits per payload bit (default: the baseline's value from `SYNDROME_FRACTIONS`) |
| `--no-reconciliation` | Use the paper's mapping without step 7's error correction |
| `--rows` | Boxes and checks shown per table (a block has 512 boxes) |

## Benchmarks

The benchmark package (`src/qsdc/benchmark/`) runs a protocol's simulator over
studies and writes their reports. It has one suite per protocol in
`studies/<protocol>/`, each extending `Suite` from `benchmark/suite.py`:

| File | Contents |
| --- | --- |
| `suite.py` | Runs the simulator, measures its transmissions, and names the report's settings and symbols |
| `studies.yaml` | The studies |

`studies/catalog.py` builds a suite's studies from its `studies.yaml`.
`report/` writes the reports; its `templates/` holds each protocol's report in
`<protocol>/report.html`, and the shared study index and stylesheet.

### Running

```bash
benchmark srikara list                                  # list the studies
benchmark srikara run                                   # run every study
benchmark srikara run --study theta_band --repetitions 3
benchmark srikara run --payload-bits 1024 --output-root src/qsdc/benchmark/results/srikara-1024
benchmark srikara run --skip-existing                   # resume an interrupted run
benchmark srikara index                                 # rebuild the study index
benchmark srikara rerender                              # rebuild reports without simulating
```

`benchmark cao` takes the same commands. Each protocol writes to
`src/qsdc/benchmark/results/<protocol>/`, wherever the command runs from;
`--output-root` writes elsewhere.

- `--repetitions N` reruns every case with N seeds and pools their counts. The
  first seed is the configured one.
- `--payload-bits N` sends a random N-bit payload in every case (default:
  10,000). Runs with another size belong in their own `--output-root`: the
  index links the latest run of each study, whatever its size.
- `--skip-existing` skips studies that already have a report.
- `rerender` rebuilds the plots, CSV and HTML from each `results.json`.

To replay one saved case and repetition with its original settings and
seeds, use `benchmark srikara reproduce path/to/results.json --case 28 --repetition 4`.
Both numbers start at 1. This compares the metrics with the saved repetition,
excluding elapsed time. It writes no reports and exits with status 1 if the metrics
differ. Reproduction uses the currently installed simulator code.

### Presets

Each protocol names its simulator configurations in its `presets.yaml`. A
preset may extend another and change its fields.

**Srikara.** `best_qp` and `aligned` extend `baseline`; every later preset
extends the row above it:

| Preset | Change |
| --- | --- |
| `baseline` | The paper's protocol: `sf-sampled`, θ uniform over 0 to 2π, 3σ checks, r = 0.576 (5 dB) |
| `best_qp` | `baseline` with `best_qp` measurement |
| `aligned` | `baseline` with `aligned` measurement |
| `gray` | Gray labels |
| `optimized` | θ uniform within 3π/2 ± π/4 |
| `parity` | Parity error detection |
| `retry` | Up to 3 attempts |
| `ldpc` | `optimized` with transmitted LDPC codewords |

**Cao.**

| Preset | Change |
| --- | --- |
| `paper` | The paper's mapping without error correction: a block is released only when every box passes its detection and parity bits |
| `reconciled` | The defaults: reconciliation and privacy amplification |
| `retry` | `reconciled` with up to 3 attempts |

### Noise baselines

The baselines are in `src/qsdc/common/config/noises.yaml`, with the source of
each value, and both protocols use them. A baseline is one fibre pass, one
memory and one detector; Srikara uses the fibre in both directions:

| Baseline | Fibre per pass | Excess noise | Detectors | Memory |
| --- | --- | --- | --- | --- |
| `clean` | none | 0 | ideal | ideal |
| `lab` | 1 km spool | 0.002 SNU | η = 0.95, 0.01 SNU | 0.95 |
| `metro_5km` | 5 km | 0.005 SNU | η = 0.85, 0.05 SNU | 0.9 |
| `metro_10km` | 10 km | 0.01 SNU | η = 0.8, 0.1 SNU | 0.9 |
| `record_27km` | 27.27 km, ultralow loss | 0.0015 SNU | η = 0.613, 0.122 SNU | 0.9 |

`record_27km` is the shortest link of Zhang et al., PRL 125, 010502 (2020).

### Studies

A study either lists its cases or sweeps one or two axes. Cases change fields
by dotted path, such as `noise.forward.transmittance`. Each noise baseline is
one series in the report. Each case sends a random 10,000-bit payload unless
`--payload-bits` says otherwise.

**Srikara** has 19 studies. A case runs `optimized` unless the study says
otherwise.

| Group | Studies | Noise |
| --- | --- | --- |
| Reference | `ideal_backend_check`, `paper_baseline`, `noise_profiles` | `clean`; `noise_profiles` uses all five |
| Signal | `squeezing_r`, `squeezing_distributions`, `theta_fixed`, `theta_band`, `r_theta_heatmap` | `lab` |
| Optimizations | `optimization_comparison`, `axis_comparison`, `interval_comparison`, `error_correction_comparison` | all five |
| Protocol | `tolerance_safety`, `one_probability` | `lab` |
| Hardware | `channel_transmittance`, `thermal_occupation`, `detector_efficiency`, `electronic_noise`, `memory_efficiency` | `lab` |

`error_correction_comparison` covers no coding, parity, SECDED and LDPC, with
retry variants for parity, SECDED and LDPC.

`optimization_comparison` also includes LDPC and LDPC with retries as alternatives
to parity, both starting from `optimized`.

**Cao** has 4 studies. A case runs `reconciled` unless the study says
otherwise.

| Group | Studies | Noise |
| --- | --- | --- |
| Reference | `noise_profiles`, `paper_comparison` | all five for `noise_profiles`; `clean` and `lab` for `paper_comparison`, which compares the presets |
| Postprocessing | `syndrome_fraction` | `clean`, `lab`, `metro_5km` |
| Signal | `squeezing_r` | `clean`, `lab` |

### Custom benchmarks

A `Benchmark` is a suite, a name, its `Case`s and its axis names: no axes gives
a comparison, one a sweep, two a heatmap. A `Case` is a simulator configuration,
a `Workload` (payload size, probability of a one, seed), a series, an optional
label and its coordinates `at`.

```python
from qsdc.benchmark.benchmark import Benchmark, Case, Workload, run_benchmark
from qsdc.benchmark.report.report import write_report
from qsdc.benchmark.studies.srikara.suite import SRIKARA
from qsdc.protocols.srikara.config import PRESETS

cases = tuple(
    Case(PRESETS["optimized"], Workload(payload_bits=1024, one_probability=p), at=(p,))
    for p in (0.1, 0.5, 0.9)
)
benchmark = Benchmark(SRIKARA, "one_probability", cases, axes=("Probability of one",))
print(write_report(run_benchmark(benchmark), SRIKARA.output_root) / "report.html")
```

`CAO` in `qsdc.benchmark.studies.cao.suite` does the same for Cao.

### Output

Each run writes `<output-root>/<study>/run_<time>/`, and
`<output-root>/index.html` links the latest run of every study.

| File | Contents |
| --- | --- |
| `report.html` | One row per case, plots, sent vs. decoded symbol tables, shared parameters |
| `results.json` | Each case's configuration, counts, rates and per-repetition counts |
| `runs.csv` | One row per case: configuration, axes, metrics and symbol counts |

### Metrics

`benchmark/metrics.py` records counts and derives every rate from them; each
suite's `measure` takes the counts from its protocol's transmission.
Repetitions are pooled by adding their counts. A send is one block in one
attempt; a released block is one whose attempt passed its security tests and
whose code then decoded it. For Cao, a state is an EPR pair and a symbol is a
box with its detection bit.

| Metric | Definition |
| --- | --- |
| Bit error rate | Wrong bits / bits in released blocks (undefined if nothing was released) |
| Erasure rate | Bits in blocks never released / payload bits |
| Delivered | Correct released bits / payload bits |
| Delivered bits per state | Correct released bits / all prepared states, retries included |
| Raw bit error rate | Wrong symbol bits before correction / symbol bits measured, code bits included |
| Raw-symbol MI per state | Mutual information between sent and decoded symbols × symbols measured / prepared states |
| Check failure rate | Failed checks / checks made |
| Aborted attempts | Attempts ended because a security test failed |
| Uncorrectable | Sends whose attempt passed the checks but whose code found an error it could not correct |
