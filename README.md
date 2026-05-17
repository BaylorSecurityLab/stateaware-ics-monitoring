# stateaware-ics-monitoring

## Stage 4 — GFSM (`gfsm-build`)

Stage 4 ("GFSM builder") is a faithful Python port of the Rust
`fsm-extractor` (`github.com/LaBackDoor/fsm-extractor`, pinned commit
`14950d5`) plus a new synchronous-product composer. It reads Stage 2's
`<plc>.ast.xml` files, extracts each PLC's local FSM, and composes them into
one global FSM per topology.

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

The port is pinned by port-fidelity golden tests that diff Python JSON/DOT
against the Rust binary; behavioral divergence fails CI.

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