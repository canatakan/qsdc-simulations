# Srikara Benchmark

Benchmark configs are strict JSON files. JSON does not allow comments, so use
this README as the annotated reference and copy `configs/smoke.json` when
making a runnable config.

Run a config with:

```bash
srikara-benchmark srikara/benchmark/configs/smoke.json
srikara-benchmark path/to/config.json --output srikara/benchmark/results/custom
```

`output_dir` is the parent output directory. Each benchmark invocation writes
artifacts inside a child run directory named like:

```text
run_1780576634533154000/
```

## Full Runnable Shape

```json
{
  "name": "smoke",
  "backend": "analytic",
  "random_source": "classical",
  "payload_bit_count": 12,
  "trials_per_combo": 2,
  "base_seed": 1000,
  "output_dir": "srikara/benchmark/results/smoke",
  "one_probabilities": [0.1, 0.5, 0.9],
  "tolerances": {
    "kind": "explicit",
    "values": [0.0000001, 0.05]
  },
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
"name": "smoke"
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

`output_dir`

Optional parent directory for generated artifacts. If omitted, defaults to:

```text
srikara/benchmark/results/<name>
```

Every benchmark run creates a child directory under this path:

```json
"output_dir": "srikara/benchmark/results/my-benchmark"
```

`one_probabilities`

Required non-empty array. Each value must be between `0.0` and `1.0`.
Benchmark message bits are generated independently with this probability of
bit `1`.

```json
"one_probabilities": [0.1, 0.5, 0.9]
```

## Tolerance Sweep

Exactly one tolerance sweep object is used per config.

Explicit values:

```json
"tolerances": {
  "kind": "explicit",
  "values": [0.0000001, 0.01, 0.05]
}
```

Linear sweep:

```json
"tolerances": {
  "kind": "linear",
  "start": 0.0,
  "stop": 0.2,
  "step": 0.01
}
```

All tolerance values must be non-negative. Linear `step` must be positive, and
`stop` must be greater than or equal to `start`.

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
one_probability x tolerance x r_distribution
```

For example:

```text
3 one_probabilities * 2 tolerances * 2 r distributions = 12 combos
```

Then it runs:

```text
12 combos * trials_per_combo
```

protocol trials.
