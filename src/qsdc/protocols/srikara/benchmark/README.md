# Srikara Benchmark

Benchmark configs are strict JSON files. JSON does not allow comments, so use
this README as the annotated reference and copy
`src/qsdc/protocols/srikara/benchmark/configs/test.json` when making a runnable config.

Run a config with:

```bash
srikara-benchmark src/qsdc/protocols/srikara/benchmark/configs/test.json
srikara-benchmark path/to/config.json --output results/srikara/benchmark/custom
```

`output_dir` is the parent output directory. Each benchmark invocation writes
artifacts inside a child run directory named like:

```text
run_1780576634/
```

## Full Runnable Shape

```json
{
  "name": "test",
  "backend": "analytic",
  "random_source": "classical",
  "payload_bit_count": 12,
  "trials_per_combo": 2,
  "base_seed": 1000,
  "tolerance_sigmas": 1.0,
  "output_dir": "results/srikara/benchmark/test",
  "one_probabilities": [0.1, 0.5, 0.9],
  "r_distributions": [
    {
      "kind": "uniform",
      "lower": 0.05,
      "upper": 0.2
    },
    {
      "kind": "fixed",
      "value": 0.4
    }
  ],
  "alpha_distribution": {
    "kind": "uniform_square",
    "bound": 2.0
  },
  "theta_distribution": {
    "kind": "uniform",
    "lower_pi": 0.0,
    "upper_pi": 2.0
  }
}
```

## Top-Level Fields

`name`

Benchmark name used in metadata and the default output path. Defaults to
`"benchmark"` if omitted.

```json
"name": "test"
```

`backend`

One backend per config. Defaults to `"sf-sampled"` if omitted.

Allowed values:

```json
"backend": "analytic"
```

```json
"backend": "sf"
```

```json
"backend": "sf-sampled"
```

`analytic` is deterministic and fast. `sf` and `sf-sampled` require the
Strawberry Fields dependency.

`random_source`

Protocol random source for routing, axes, Bob preparation, and message values.
Defaults to `"classical"` if omitted.

Allowed values:

```json
"random_source": "classical"
```

```json
"random_source": "sf-bs-qrng"
```

`sf-bs-qrng` is a Quantum Random Number Generator with a beam splitter using
Strawberry Fields.

`payload_bit_count`

Required positive integer. Number of classical payload bits Alice wants to send
per trial, before any padding is added.

The simulator pads this payload with zero bits until its length is divisible by
3, because each protocol message mode carries one 3-bit interval symbol.

Derived counts:

```text
padding_bit_count = (-payload_bit_count) mod 3
transmitted_message_bit_count = payload_bit_count + padding_bit_count
message_symbol_count = transmitted_message_bit_count / 3
message_mode_count = message_symbol_count
n_states = 4 * message_mode_count
```

Example:

```json
"payload_bit_count": 16
```

This derives:

```text
padding_bit_count = 2
transmitted_message_bit_count = 18
message_symbol_count = 6
message_mode_count = 6
n_states = 24
```

`trials_per_combo`

Positive integer. Number of repeated protocol trials per parameter combination.
Defaults to `1` if omitted.

```json
"trials_per_combo": 100
```

`base_seed`

Integer seed used to derive per-trial message and simulation seeds. Defaults to
`0` if omitted.

```json
"base_seed": 1000
```

`tolerance_sigmas`

Optional non-negative number. This is the control/decoy check threshold in
measurement noise sigmas. If omitted, the backend default is used. Current
backend defaults are `1.0` for exact backends and `4.0` for `sf-sampled`.

```json
"tolerance_sigmas": 4.0
```

`output_dir`

Optional parent directory for generated artifacts. If omitted, defaults to:

```text
results/srikara/benchmark/<name>
```

Every benchmark run creates a child directory under this path:

```json
"output_dir": "results/srikara/benchmark/my-benchmark"
```

`one_probabilities`

Required non-empty array. Each value must be between `0.0` and `1.0`.
Benchmark message bits are generated independently with this probability of
bit `1`.

```json
"one_probabilities": [0.1, 0.5, 0.9]
```

## Squeezing r Distributions

`r_distributions` is required and must contain at least one distribution. This
is a sweep dimension, so each listed distribution creates benchmark combos.

Uniform range:

```json
{
  "kind": "uniform",
  "lower": 0.05,
  "upper": 0.2
}
```

Fixed value:

```json
{
  "kind": "fixed",
  "value": 0.4
}
```

Validation rules:

- uniform `lower >= 0`
- uniform `upper >= lower`
- fixed `value >= 0`

## Alpha Distribution

Optional. Defaults to:

```json
"alpha_distribution": {
  "kind": "uniform_square",
  "bound": 2.0
}
```

Currently supported option:

```json
"alpha_distribution": {
  "kind": "uniform_square",
  "bound": 2.0
}
```

This samples Bob's alpha from a square in the complex plane:

```text
real(alpha), imag(alpha) ~ uniform(-bound, bound)
```

Validation rule:

- `bound >= 0`

## Theta Distribution

Optional. Defaults to a uniform full rotation:

```json
"theta_distribution": {
  "kind": "uniform",
  "lower_pi": 0.0,
  "upper_pi": 2.0
}
```

Theta config values are expressed in multiples of pi radians.

Uniform interval:

```json
"theta_distribution": {
  "kind": "uniform",
  "lower_pi": 0.0,
  "upper_pi": 2.0
}
```

Fixed value:

```json
"theta_distribution": {
  "kind": "fixed",
  "value_pi": 0.5
}
```

## Combo Expansion

The benchmark creates one combo for each Cartesian product of:

```text
one_probability x r_distribution
```

For example:

```text
3 one_probabilities * 2 r distributions = 6 combos
```

Then it runs:

```text
6 combos * trials_per_combo
```

protocol trials.

## Artifacts

Each benchmark run writes these artifacts into its `run_<unix_seconds>/`
directory:

```text
benchmark.json
config.json
combos.json
benchmark.xlsx
trials.jsonl
plots/
```

`benchmark.json` is the run summary. It records the run id, derived protocol
counts, aggregate acceptance rate, elapsed time, and the relative paths of all
written artifacts.

`config.json` is the effective runnable config for that run. It can be loaded
again with `srikara-benchmark`.

`combos.json` contains one aggregate object per parameter combo. Each combo has
top-level rates for acceptance and protocol checks, plus nested metric groups:

```text
all
accepted
rejected
```

`benchmark.xlsx` is the human-readable Excel workbook. It groups the benchmark
views into separate sheets:

```text
Run              run metadata and derived protocol counts
Overview         acceptance and protocol pass rates per combo
Errors           bit, symbol, numeric, and accepted/rejected error metrics
Checks           control/decoy check counts and failed-check severity
Tolerance        configured sigma tolerance, noise sigma, and derived thresholds
Trial Tolerance  per-trial required control/decoy/acceptance tolerances
```

`trials.jsonl` contains one JSON object per protocol trial.

`plots/` contains matplotlib PNG plots generated from `combos.json` and
`trials.jsonl`:

```text
bit_error_by_r.png
symbol_error_by_r.png
value_error_by_r.png
derived_acceptance_tolerance_sigmas_curve.png
```

The threshold curve is derived from observed control and decoy deviations. For
each trial, `required_acceptance_tolerance_sigmas` is the smallest tolerance,
in measurement noise sigmas, that would accept that observed trial. The maximum
required tolerance in a combo is the empirical threshold that would accept every
observed trial in that combo.

Existing run artifacts can be plotted again with:

```bash
srikara-benchmark-plot path/to/run_<unix_seconds>
```

The code that writes runtime artifacts is grouped under
`src/qsdc/protocols/srikara/benchmark/artifacts/`. Generated benchmark outputs
still go to the configured `output_dir`; they are not source files.
