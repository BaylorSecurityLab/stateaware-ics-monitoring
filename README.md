# stateaware-ics-monitoring

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