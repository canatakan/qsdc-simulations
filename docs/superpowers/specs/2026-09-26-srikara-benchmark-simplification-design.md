# Srikara benchmark simplification

## Intent and scope

Make a benchmark easy to declare, execute, and inspect without empty layout
subclasses, duplicate run collections, callback wrappers, or result objects that
only mirror other result objects. The current staged migration is the starting
point. Its files and generated result folders must be preserved while the
refactor is developed. Public Python names, CLI text, and artifact schema do not
need backward compatibility.

The benchmark remains a set of one-time Srikara transmissions arranged for
comparison, a one-dimensional sweep, or a two-dimensional heatmap. Keep the
existing 19 built-in studies in this refactor. Retain measurements that
explain exact recovery, partial useful delivery, errors, erasures, checks,
correction, retries, state use, and time; remove measurements only when they are
duplicates with no distinct interpretation.

## Benchmark declarations

`RunSpec` remains a validated pair of `SimulatorConfig` and `WorkloadConfig`.
One `RunSpec` means one payload transmission. A single concrete `Benchmark`
stores its name, a layout value (`comparison`, `sweep`, or `heatmap`), an ordered
tuple of cases, and the axis names needed by plots. A case stores its `RunSpec`,
series name, optional numeric `x` and `y` coordinates, and optional comparison
label. Case identifiers are derived from order when results are produced.

The benchmark exposes its count and specifications from its cases; it does not
store a second `runs` tuple. Short `comparison`, `sweep`, and `heatmap`
construction helpers build this one model from cases and check the coordinates
required by the selected layout. Study declarations pair coordinates with
`RunSpec` values when constructing cases. They assign series names directly;
there is no `Grouping` object or reader callback. Axis names live with the
benchmark instead of in a table keyed by benchmark name.

Construction checks only what execution or plotting needs: a study has at least
one case; comparisons have no axis coordinates, sweeps have `x` only, and
heatmaps have both; each heatmap series has one value per cell in its own
rectangular grid. The code does not add a general validation framework or
recheck these invariants throughout execution and reporting.

## Execution and measurements

`BenchmarkRunner` executes cases in order and returns a `BenchmarkResult`.
It generates one payload for each distinct `WorkloadConfig` before simulation,
so cases sharing a workload receive identical input bits. Each case executes
exactly once with its own `SimulatorConfig`.

A run result owns the case, input bits, protocol result, elapsed time, and
measurements. A benchmark result owns its benchmark, ordered run results, and
total elapsed time. Reporting does not require `BenchmarkArtifact` or
`ArtifactManifest` mirrors, and the runner does not write files. The reporting
writer is called explicitly after a successful run.

Keep a typed measurement record for quantities with scientific meaning. Store
primary counts and durations once, deriving simple ratios from them so counts
and rates cannot disagree. An undefined ratio, such as bit error rate when no
bits were recovered, is represented as `None`. Exact payload recovery remains
separate from correctly delivered payload bits in partially successful runs.
Summary values aggregate counts first and then calculate rates from aggregate
denominators. Simulation and workload configuration stay out of presentation
formatting.

## Catalog, presets, and output

Replace per-number enum classes with named preset data: mappings for named
noise and simulator configurations, and short tuples for numeric sweep values.
Use small pure functions for noise variations that need to replace channel,
detector, readout, or memory settings. Build validated configurations rather
than relying on unvalidated `model_copy(update=...)` results. Keep one
`expand_runs` helper for repeated Cartesian products. It preserves unspecified
simulator settings and distinguishes omitted selections from explicit empty
selections.

The built-in catalog continues to expose the useful comparison, sweep, and
heatmap studies. Repeated declaration code can be consolidated without hiding
which simulator and workload values each case uses. The CLI retains practical
list, single-study, all-study, and index operations, but its Python API and
printed text may change.

One reporting entry point accepts a `BenchmarkResult` and an output root, then
writes JSON, CSV, HTML, and plots in a new execution directory. JSON has one
top-level benchmark descriptor (name, layout, axis names), one summary, and an
ordered `runs` array. Each run records its case identifier, series, coordinates,
label, complete `RunSpec`, and measurements. CSV carries one row per run with
the configuration fields needed to reproduce it. The HTML
report and plots read the same result; the index reads the new JSON shape.
Presentation labels and colors stay in the reporting layer except for the axis
names supplied by a benchmark declaration. Existing result directories are
left untouched.

## Failure behavior and verification

Invalid layout coordinates or an incomplete heatmap fail when constructing the
benchmark, with a short error naming the issue. Simulation errors propagate
with the case position identifiable. Reporting begins only after all cases
execute, so a failed simulation produces no new report directory. Avoid broad
defensive branches for conditions the typed inputs and construction checks
already rule out.

Focused tests cover case construction, shared workload input, exactly one
simulation per case, count and rate edge cases, heatmap rendering, and a small
CLI-to-report flow. Update the README examples and output description. Run the
repository's Python tests, scoped lint, and diff checks after implementation;
the full expensive benchmark catalog is not required for verification.
