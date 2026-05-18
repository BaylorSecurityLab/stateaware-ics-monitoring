# stateaware-ics-monitoring

## Stage 4 — GFSM (`gfsm-build`)

Stage 4 ("GFSM builder") implements the paper-faithful FSM extraction
algorithm (Def 1/2: one FunctionBlock per CASE variable per PLC) plus a new
synchronous-product composer. It is derived from the Rust `fsm-extractor`
(`github.com/LaBackDoor/fsm-extractor`, pinned commit `14950d5`) but
intentionally supersedes its lead-actuator-only behavior for multi-actuator
PLCs. It reads Stage 2's `<plc>.ast.xml` files, extracts each PLC's local
FSM, and composes them into one global FSM per topology.

```bash
gfsm-build --topology anytown
# or every topology with a Stage 2 analysis manifest:
gfsm-build --all
```

For each PLC it writes into `data/generated/<topology>/gfsm/`:
`<plc>.fsm.json`, `<plc>.fsm.dot`; per topology `<topology>.gfsm.json`,
`<topology>.gfsm.dot`, `<topology>.gfsm.analysis.json`, plus
`<topology>_gfsm_manifest.json` (provenance + per-PLC status, cross-checked
against Stage 2's FSM counts).

Flags: `--max-states N` (hard cap on global states; clean error on
overflow), `--out-dir PATH`, `--jobs N` (process-pool fan-out across PLCs;
`--jobs 1` is sequential; output is byte-identical regardless of `N`).

Correctness is enforced by the structural golden tests in
`tests/gfsm/test_golden_*.py`; they verify per-CASE FSM structure and
composition against known-good fixtures.

## Stage 2 — ST analysis (`st-analyze`)

Stage 2 ("parser") runs the vendored IEC-ST-Analyzer (`src/iec_st_compiler/`,
upstream `github.com/LaBackDoor/iec_st_compiler`) over `st_gen`'s generated
`.st` files to produce the AST / PDG / invariant-template artifacts consumed by
Stage 3 (STL synthesis) and Stage 4 (GFSM extraction).

```bash
st-analyze --topology anytown
# or every topology with a manifest:
st-analyze --all
```

For each PLC it writes into `data/generated/<topology>/analysis/`:
`<plc>.ast.xml`, `<plc>.invariants.json`, `<plc>.pdg.dot`, `<plc>.pdg.json`,
plus `<topology>_analysis_manifest.json` (provenance + per-PLC status,
cross-checked against `st_gen`'s FSM counts).

The vendored analyzer is never modified; any dialect mismatch is fixed in
`st_gen`'s emitter or `st_analyze/adapter.py`.

## Stage 3 — STL monitor (`stl-monitor`) + hybrid (`ics-monitor`)

`dataio-ingest --all` normalizes the raw attack datasets (anytown 7z, **ctown =
BATADAL**, ltown zarr) into committed `data/<topo>/dataset/` via the shared
`src/dataio/` loader (also consumed by the future invariant quantifier).
`stl-monitor --topology <t>` (or `--all`) calibrates STL thresholds from the
clean frames, synthesizes formulas, evaluates robustness with `rtamt`
(per-formula `--jobs` parallel, byte-identical regardless of worker count), and
writes `data/generated/<topo>/stl/`. `ics-monitor` runs the STL detector plus a
documented all-zeros GFSM stub and emits the logical-OR label
(`data/generated/<topo>/monitor/`); the GFSM stub is replaced when Stage 4's
runtime detector lands, with no change to fusion/CLI.

`rtamt` has no usable PyPI release on Python ≥3.13; it is pinned from git with a
`typing.io` shim — see `INSTALL.md`. BATADAL provenance (it *is* the C-Town
network) is recorded only in `data/ctown/dataset/dataset_manifest.yaml`; the
ltown reader self-calibrates tank elevation/level from the zarr archive.

## Stage "invariants" — NiaARM state-aware mining (`invariants-mine`)

Implements Algorithm 1 of the SAIN paper: per composite GFSM state `s`,
mine numerical association rules with NiaARM from baseline calibration
traces sliced to `Ds`, filter to confidence ≥ 0.7 and support ≥ 0.1, and
persist the invariant mapping `Φ(s)`.

```bash
invariants-mine --topology anytown --data-root data
# or every topology that has data/generated/<topo>/gfsm/<topo>.gfsm.json:
invariants-mine --all --data-root data
```

Writes `data/generated/<topo>/invariants/<topo>_phi.json` +
`<topo>_invariants_manifest.json` (provenance + sha256 of the upstream
gfsm and dataset manifests).

The data column for each GFSM component (one per actuator CASE) is
resolved automatically per-actuator from the CASE selector
(`<ACT>_State` → actuator `ACT`) through the dataset `column_map`
(`ACT` → `S_`+`ACT` → lowercase fallback) — no manual configuration. The runtime
monitor (`ics-monitor`) consumes `Φ` and the GFSM JSON, loaded once at
`fit()` (build-once / reuse-many; staleness-gated by sha256). Fusion
defaults to the paper's intersection rule `(gfsm OR invariants) AND stl`;
pass `--fusion or` for the baseline.