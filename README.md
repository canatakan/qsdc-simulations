# QSDC Simulations

Simulators for two continuous-variable quantum secure direct communication
(QSDC) protocols, [Srikara](#srikara) and [Cao](#cao), with demos that walk
through one transmission and a [benchmark](#benchmarks) runner that writes
HTML reports.

## Quick start

Requires Python 3.9.

```bash
python -m venv .venv
source .venv/bin/activate
make install
```

```bash
make test

# Run demos
srikara-demo "hello"
cao-demo "hello"

# View and run benchmarks
benchmark srikara list
benchmark srikara run --study noise_profiles --payload-bits 1024
```

Reports are written to `src/qsdc/benchmark/results/<protocol>/index.html`.

## Layout

| Path | Contents |
| --- | --- |
| `src/qsdc/protocols/<protocol>/` | Simulator, backends, config and `presets.yaml` |
| `src/qsdc/common/` | Coding (parity, SECDED, LDPC, universal hash), noise models, random sources |
| `src/qsdc/benchmark/` | Runner, metrics, CLI, per-protocol suites and `studies.yaml`, HTML reports |
| `src/qsdc/demo/` | `srikara-demo` and `cao-demo` |
| `tests/` | Tests, laid out like `src/` |

## Srikara

> S. Srikara, K. Thapliyal, and A. Pathak, Continuous variable direct secure
> quantum communication using gaussian states, Quantum Inf. Process. 19, 1 (2020).

Each 3-bit symbol uses 4 squeezed coherent states over two optical passes:

1. Bob prepares the states with random α, r and θ and sends them to Alice.
2. Alice checks half of them (the controls) against the values Bob reveals.
3. Alice displaces a quarter (the messages) by m(1 + i), where the interval of
   m encodes 3 bits, and returns them with the last quarter (the decoys).
4. Bob checks the decoys and decodes m from the messages.

A check passes within k = `tolerance_sigmas` standard deviations of its
expected value. The controls and the decoys of an attempt each form a security
test, which passes when at most `q + k · √(q(1 − q)/n)` of its n checks fail,
with `q = erfc(k/√2)`. A failed test aborts the attempt.

```python
from qsdc.protocols.srikara.config import SimulatorConfig
from qsdc.protocols.srikara.simulator.protocol import Simulator

config = SimulatorConfig(error_correction="secded", max_attempts=3)
transmission = Simulator(config).transmit("101001110010")
assert transmission.recovered_bits == "101001110010"
```

`SimulatorConfig` defaults to the noiseless paper setting. Its main options:

| Option | Values |
| --- | --- |
| `backend` | `analytic` (the paper's algebra, ignores noise), `sf` (Strawberry Fields, exact means), `sf-sampled` (Strawberry Fields, homodyne samples) |
| `axis_policy` | `random` (q or p, as in the paper), `best_qp` (whichever responds more), `aligned` (along the unsqueezed displacement) |
| `intervals` | `default` (binary labels), `gray`, `gaussian_gray` (Cao et al.'s equiprobable intervals) |
| `error_correction` | `none`, `parity`, `secded` (three interleaved Hamming (8, 4) codewords), `ldpc` (soft-decision, configured by `LdpcConfig`) |
| `max_attempts` | Attempts per message; blocks that fail their checks or code are resent |

The Strawberry Fields backends model a thermal loss channel in each direction,
Alice's memory, and each detector's efficiency and electronic noise. The
message signal is strongest for `aligned` at θ = 3π/2 and weakest at θ = π/2.

## Cao

> Z. Cao, L. Wang, K. Liang, G. Chai, and J. Peng, Continuous-variable quantum
> secure direct communication based on Gaussian mapping, Phys. Rev. Appl. 16,
> 024012 (2021).

Alice keeps half of each two-mode squeezed pair and sends the other to Bob:

1. Two squeezed vacua on a 50:50 beam splitter give S1 (Alice) and S2 (Bob).
2. **Channel detection:** both heterodyne positions Alice picks. A position
   passes when X_m² + P_m² < 2 (Duan's criterion).
3. **Authentication:** the same test on positions Bob picks.
4. **Gaussian mapping:** each 2-bit box gets a random detection bit and selects
   one of 8 equiprobable intervals of N(0, V_A); G1' is drawn inside it.
5. Alice displaces S1 by G1' in X and an independent Gaussian G2 in P.
6. Bob measures the arriving beam jointly with S2.
7. **Postprocessing:** Bob estimates his gain from G2, reconciles with an LDPC
   syndrome from Alice, and the message is the universal hash of the payload.

```python
from qsdc.protocols.cao.config import SimulatorConfig
from qsdc.protocols.cao.simulator.protocol import Simulator

transmission = Simulator(SimulatorConfig(max_attempts=3)).transmit("1010")
```

It has the same three backends as Srikara, with `sf-sampled` as the default. A
block has 512 boxes. The paper gives no check threshold, so a security test
passes when at most q + `check_tolerance_sigmas` · √(q(1 − q)/n) of its checks
fail, with q = e^(−1/σ²) the honest failure rate. Each announced parity and
syndrome bit costs one message bit; `SYNDROME_FRACTIONS` holds the smallest
fraction that reconciles every block on each baseline:

| Baseline | Syndrome fraction | Message bits per block |
| --- | --- | --- |
| `clean` | 0.10 | 378 |
| `lab` | 0.25 | 224 |
| `metro_5km` | 0.40 | 70 |
| `metro_10km`, `record_27km` | none | — |

`reconciliation=None` uses the paper's mapping instead, which releases a block
only when every box passes its detection and parity bits.

## Benchmarks

```bash
benchmark srikara list                       # list the studies
benchmark srikara run                        # run every study
benchmark srikara run --study theta_band --repetitions 3
benchmark srikara run --skip-existing        # resume an interrupted run
benchmark srikara rerender                   # rebuild reports from results.json
benchmark srikara reproduce path/to/results.json --case 28 --repetition 4
```

`benchmark cao` takes the same commands. Other options: `--workers N`
(parallel studies, default 4), `--payload-bits N` (default 10,000) and
`--output-root DIR`. Each run writes `report.html`, `results.json` and
`runs.csv` to `<output-root>/<study>/run_<time>/`.

### Presets

Named configurations in each protocol's `presets.yaml`; a preset may extend
another.

| Srikara | |
| --- | --- |
| `baseline` | The paper: `sf-sampled`, θ uniform over [0, 2π), 3σ checks, r = 0.576 (5 dB) |
| `best_qp`, `aligned` | `baseline` with that measurement axis |
| `gray` | `aligned` with Gray labels |
| `optimized` | `gray` with θ uniform within 3π/2 ± π/4 |
| `parity`, `retry` | `optimized` with parity, then up to 3 attempts |
| `ldpc`, `ldpc_large` | `optimized` with LDPC (96 + 96 bits, or 384 + 768 bits) |

| Cao | |
| --- | --- |
| `paper` | The paper's mapping without error correction |
| `reconciled` | Reconciliation and privacy amplification |
| `retry` | `reconciled` with up to 3 attempts |

### Noise baselines

Shared by both protocols in `src/qsdc/common/config/noises.yaml`, with sources.
Each is one fibre pass, one memory and one detector.

| Baseline | Fibre per pass | Excess noise | Detectors | Memory |
| --- | --- | --- | --- | --- |
| `clean` | none | 0 | ideal | ideal |
| `lab` | 1 km | 0.002 SNU | η = 0.95, 0.01 SNU | 0.95 |
| `metro_5km` | 5 km | 0.005 SNU | η = 0.85, 0.05 SNU | 0.9 |
| `metro_10km` | 10 km | 0.01 SNU | η = 0.8, 0.1 SNU | 0.9 |
| `record_27km` | 27.27 km, ultralow loss | 0.0015 SNU | η = 0.613, 0.122 SNU | 0.9 |

### Studies

Srikara has 20 studies grouped as reference, signal (squeezing, θ), optimizations
(axis, intervals, error correction, LDPC configuration), protocol and hardware
sweeps. Cao has 4: noise profiles, paper comparison, syndrome fraction and
squeezing. `benchmark <protocol> list` prints them; their definitions are in
`studies/<protocol>/studies.yaml`.

### Metrics

| Metric | Definition |
| --- | --- |
| Bit error rate | Wrong bits / bits in released blocks |
| Erasure rate | Bits in blocks never released / payload bits |
| Delivered | Correct released bits / payload bits |
| Delivered bits per state | Correct released bits / all prepared states |
| Raw bit error rate | Wrong symbol bits before correction / symbol bits measured |
| Raw-symbol MI per state | Mutual information between sent and decoded symbols per prepared state |
| Check failure rate | Failed checks / checks made |
| Coding rejection rate | Sends that passed the checks but could not be decoded / all sends |
| Aborted attempts | Attempts ended by a failed security test |

Repetitions are pooled by adding their counts.
