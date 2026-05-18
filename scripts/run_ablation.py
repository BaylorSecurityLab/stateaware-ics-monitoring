"""End-to-end GFSM/STL/OR ablation for the state-aware ICS monitoring pipeline.

Runs the WHOLE shipped pipeline for every topology (anytown, ctown, ltown):

  1. Regenerate artifacts idempotently:
        python -m gfsm --all
        python -m invariants --all --data-root data
  2. Run the shipped hybrid monitor with OR fusion so per-detector columns
     are emitted to scripts/out/<T>/monitor/predictions.csv.
  3. Build three paper-faithful ablation arms from those columns:
        gfsm        = y_pred_gfsm | y_pred_invariants   (ONE state-aware
                      detector: the GFSM detector inherently includes its
                      invariant Φ-templates -- gfsm δ-conformance UNION the
                      Φ-template check).
        stl         = y_pred_stl                        (physics side)
        gfsm_or_stl = gfsm | stl
  4. Score each arm vs y_true (concatenated over all eval scenarios) using
     stl.metrics.detection_metrics so the metric definitions stay identical
     to the rest of the repo. Headline: MCC, Balanced Accuracy, AUPRC.
  5. Emit per-topology per-datapoint agreement CSVs and a combined metrics CSV.

NOTE on AUPRC: the ablation arms are binary detectors with no continuous
score, so the arm's 0/1 vector is passed as the score input. The resulting
average-precision is therefore a COARSE AP, not a ranking-based AUPRC.

This script does NOT re-implement detector wiring -- it shells out to the
already-shipped, reviewed `gfsm`, `invariants` and `monitor` CLIs and only
post-processes their predictions.csv.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

# Repo `src/` is import-rooted; reuse the repo's own metric definitions so the
# ablation numbers are consistent with stl / monitor.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from stl.metrics import detection_metrics  # noqa: E402

TOPOLOGIES = ["anytown", "ctown", "ltown"]

CAVEAT = (
    "CAVEAT: The GFSM is currently UNDER-COMPOSED. src/gfsm extracts only the "
    "lead actuator's CASE per PLC (e.g. ctown_plc3.fsm.json has 1 function_block "
    "V2_State though PLC3 controls V2,PU4,PU5,PU6,PU7), so the composite GFSM "
    "state space is far smaller than the paper's Def 1/2 product of all actuator "
    "FSMs. The 'gfsm' and 'gfsm_or_stl' arms therefore UNDERSTATE paper-faithful "
    "performance -- a Stage-4 gfsm fix is pending."
)

# Order is load-bearing: parent reporting + verify step assert this exactly.
AGREEMENT_COLS = ["scenario", "row", "y_true", "gfsm", "stl"]
METRIC_COLS = [
    "topology", "arm", "n", "attack_rows",
    "mcc", "balanced_accuracy", "auprc",
    "precision", "recall", "f1", "tp", "fp", "fn", "tn",
]


def _run(cmd: list[str], *, cwd: Path) -> tuple[int, str]:
    """Run a subprocess, capturing combined output. Returns (rc, tail)."""
    proc = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    tail = "\n".join(out.strip().splitlines()[-12:])
    return proc.returncode, tail


def _arm_metrics(y_true, y_pred) -> dict:
    """Reuse the repo metric helper. Binary detectors have no continuous
    score -> pass the binary vector as both y_pred and scores (coarse AP)."""
    m = detection_metrics(y_true, y_pred, y_pred.astype(float))
    return {
        "mcc": m["mcc"],
        "balanced_accuracy": m["balanced_accuracy"],
        "auprc": m["aucpr"],
        "precision": m["precision"],
        "recall": m["recall"],
        "f1": m["f1"],
        "tp": m["tp"], "fp": m["fp"], "fn": m["fn"], "tn": m["tn"],
    }


def _process_topology(topology: str, data_root: Path, out_root: Path,
                       repo_root: Path) -> tuple[list[dict], str]:
    """Run monitor + build arms for one topology.

    Returns (metric_rows, status). On failure metric_rows is [] and status
    is a short reason string; the caller keeps going with other topologies.
    """
    mon_out = out_root / topology / "monitor"
    mon_out.mkdir(parents=True, exist_ok=True)

    rc, tail = _run(
        [sys.executable, "-m", "monitor",
         "--topology", topology, "--data-root", str(data_root),
         "--out", str(mon_out), "--fusion", "or"],
        cwd=repo_root)
    if rc != 0:
        return [], f"monitor rc={rc}: {tail.splitlines()[-1] if tail else ''}"

    pred_csv = mon_out / "predictions.csv"
    if not pred_csv.is_file():
        return [], "monitor produced no predictions.csv"

    df = pd.read_csv(pred_csv)
    if df.empty:
        return [], "predictions.csv is empty"

    # Three paper-faithful arms.
    gfsm = (df["y_pred_gfsm"].astype(int) | df["y_pred_invariants"].astype(int))
    stl = df["y_pred_stl"].astype(int)
    gfsm_or_stl = (gfsm | stl)
    y_true = df["y_true"].astype(int)

    # Per-datapoint agreement CSV: gfsm & stl adjacent so per-row
    # agreement/disagreement is directly visible.
    agree = pd.DataFrame({
        "scenario": df["scenario"],
        "row": df["row"],
        "y_true": y_true,
        "gfsm": gfsm.astype(int),
        "stl": stl.astype(int),
    })[AGREEMENT_COLS]
    agree.to_csv(out_root / topology / f"{topology}_agreement.csv", index=False)

    arms = {"gfsm": gfsm, "stl": stl, "gfsm_or_stl": gfsm_or_stl}
    n = int(len(y_true))
    attack_rows = int(y_true.sum())
    rows: list[dict] = []
    for arm_name, y_pred in arms.items():
        m = _arm_metrics(y_true.to_numpy(), y_pred.to_numpy())
        rows.append({
            "topology": topology, "arm": arm_name,
            "n": n, "attack_rows": attack_rows, **m,
        })
    return rows, "ok"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_ablation",
        description="End-to-end GFSM/STL/OR ablation over all topologies.")
    parser.add_argument(
        "--data-root", type=Path, default=_REPO_ROOT / "data",
        help="dataio data root (default: <repo>/data)")
    parser.add_argument(
        "--out", type=Path, default=_REPO_ROOT / "scripts" / "out",
        help="output dir (default: <repo>/scripts/out)")
    parser.add_argument(
        "--skip-regen", action="store_true",
        help="skip the gfsm/invariants artifact regeneration step")
    args = parser.parse_args(argv)

    data_root: Path = args.data_root
    out_root: Path = args.out
    out_root.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print(CAVEAT)
    print("=" * 78)

    # 1. Idempotent artifact regeneration (safe to re-run). A regen failure is
    #    not fatal on its own -- committed artifacts may already exist; the
    #    monitor run will surface any genuinely missing artifact per topology.
    if not args.skip_regen:
        for label, cmd in (
            ("gfsm --all", [sys.executable, "-m", "gfsm", "--all"]),
            ("invariants --all",
             [sys.executable, "-m", "invariants", "--all",
              "--data-root", str(data_root)]),
        ):
            print(f"\n[regen] {label} ...")
            rc, tail = _run(cmd, cwd=_REPO_ROOT)
            print(f"[regen] {label} rc={rc}")
            if rc != 0:
                print(f"[regen] WARNING {label} non-zero; continuing "
                      f"(committed artifacts may already exist):\n{tail}")

    # 2-5. Per topology.
    all_rows: list[dict] = []
    statuses: dict[str, str] = {}
    for topology in TOPOLOGIES:
        print(f"\n[monitor] {topology} (fusion=or) ...")
        rows, status = _process_topology(
            topology, data_root, out_root, _REPO_ROOT)
        statuses[topology] = status
        if rows:
            all_rows.extend(rows)
            print(f"[monitor] {topology}: OK "
                  f"({rows[0]['n']} rows, {rows[0]['attack_rows']} attack)")
        else:
            print(f"[monitor] {topology}: FAILED -- {status}")

    # 6. Combined metrics CSV (+ caveat header comment line) and summary.
    metrics_csv = out_root / "ablation_metrics.csv"
    if all_rows:
        df = pd.DataFrame(all_rows, columns=METRIC_COLS)
    else:
        df = pd.DataFrame(columns=METRIC_COLS)
    df = df.copy()
    df["CAVEAT"] = CAVEAT

    with metrics_csv.open("w", encoding="utf-8", newline="") as fh:
        fh.write(f"# {CAVEAT}\n")
        df.to_csv(fh, index=False)

    print("\n" + "=" * 78)
    print("ABLATION METRICS (headline: MCC / Balanced Accuracy / AUPRC)")
    print("=" * 78)
    if all_rows:
        show = df[METRIC_COLS].copy()
        for c in ("mcc", "balanced_accuracy", "auprc",
                  "precision", "recall", "f1"):
            show[c] = show[c].map(lambda v: f"{v:.4f}")
        print(show.to_string(index=False))
    else:
        print("(no successful topologies)")

    print("\nPer-topology status:")
    for topology in TOPOLOGIES:
        print(f"  {topology:8s}: {statuses[topology]}")

    print("\n" + "=" * 78)
    print(CAVEAT)
    print("=" * 78)
    print(f"\nWrote: {metrics_csv}")
    for topology in TOPOLOGIES:
        if statuses[topology] == "ok":
            print(f"Wrote: {out_root / topology / f'{topology}_agreement.csv'} "
                  f"(cols: {','.join(AGREEMENT_COLS)})")

    n_fail = sum(1 for s in statuses.values() if s != "ok")
    # Exit non-zero only if ALL topologies failed.
    return 1 if n_fail == len(TOPOLOGIES) else 0


if __name__ == "__main__":
    sys.exit(main())
