# scripts/

## run_ablation.py

End-to-end GFSM vs STL vs OR ablation over all topologies (anytown, ctown, ltown).

```bash
python scripts/run_ablation.py
```

What it does (reuses the shipped CLIs — no detector re-implementation):

1. Idempotently regenerates artifacts: `python -m gfsm --all`,
   `python -m invariants --all --data-root data` (skip with `--skip-regen`).
2. Runs the shipped hybrid monitor with OR fusion per topology:
   `python -m monitor --topology <T> --data-root data --out scripts/out/<T>/monitor --fusion or`.
3. Builds three paper-faithful ablation arms from `predictions.csv`:
   - `gfsm`        = `y_pred_gfsm | y_pred_invariants` — ONE state-aware
     detector (GFSM δ-conformance UNION the Φ invariant-template check; the
     GFSM detector inherently includes its invariant templates).
   - `stl`         = `y_pred_stl` — physics side.
   - `gfsm_or_stl` = `gfsm | stl`.
4. Scores each arm vs `y_true` (concatenated over all eval scenarios) via
   `stl.metrics.detection_metrics` so metric definitions match the rest of
   the repo. Headline metrics: **MCC**, **Balanced Accuracy**, **AUPRC**.

### Outputs

- `scripts/out/ablation_metrics.csv` — one row per (topology, arm); columns
  `topology,arm,n,attack_rows,mcc,balanced_accuracy,auprc,precision,recall,f1,tp,fp,fn,tn`
  plus a `CAVEAT` column and a leading `#` caveat header comment line.
- `scripts/out/<T>/<T>_agreement.csv` — per-datapoint, columns exactly
  `scenario,row,y_true,gfsm,stl` (gfsm & stl adjacent for direct
  agreement/disagreement inspection).
- `scripts/out/<T>/monitor/predictions.csv` — raw monitor output.

### AUPRC note

The ablation arms are binary detectors with no continuous score, so the
arm's 0/1 vector is passed as the score input. The reported AUPRC is
therefore a **coarse average precision**, not a ranking-based AUPRC.

### CAVEAT (under-composed GFSM)

The GFSM is currently **UNDER-COMPOSED**: `src/gfsm` extracts only the lead
actuator's CASE per PLC (e.g. `ctown_plc3.fsm.json` has 1 function_block
`V2_State` though PLC3 controls V2,PU4,PU5,PU6,PU7), so the composite GFSM
state space is far smaller than the paper's Def 1/2 product of all actuator
FSMs. The `gfsm` and `gfsm_or_stl` arms therefore **understate** paper-faithful
performance — a Stage-4 gfsm fix is pending. This caveat is also printed to
stdout and embedded in `ablation_metrics.csv`.

Robustness: a topology whose monitor run fails is recorded (status) and
skipped; the script exits non-zero only if **all** topologies fail.
