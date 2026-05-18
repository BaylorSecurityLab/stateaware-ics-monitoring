"""Golden/structural test: real mine_topology on committed pipeline data."""

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from invariants.driver import mine_topology
from invariants.state_label import label_frame

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
TOPOLOGY = "ctown"
GFSM_DIR = DATA / "generated" / TOPOLOGY / "gfsm"
GFSM_JSON = GFSM_DIR / f"{TOPOLOGY}.gfsm.json"
GFSM_MANIFEST = GFSM_DIR / f"{TOPOLOGY}_gfsm_manifest.json"
DS_MANIFEST = DATA / TOPOLOGY / "dataset" / "dataset_manifest.yaml"

_DATA_PRESENT = GFSM_JSON.exists() and DS_MANIFEST.exists()
skip_no_data = pytest.mark.skipif(
    not _DATA_PRESENT, reason=f"{TOPOLOGY} gfsm/dataset not populated")


def _fb_to_col():
    from invariants.state_label import resolve_fb_to_col_from_paths
    fb_to_col, components, gfsm = resolve_fb_to_col_from_paths(
        GFSM_DIR, TOPOLOGY, DATA)
    return fb_to_col, components, gfsm


@skip_no_data
def test_mine_topology_real_data(tmp_path: Path):
    fb_to_col, components, gfsm = _fb_to_col()
    out = tmp_path / "inv"
    m = mine_topology(topology=TOPOLOGY, data_root=DATA, gfsm_dir=GFSM_DIR,
                       out_dir=out, fb_to_col=fb_to_col,
                       min_observations=50, max_evals=400, seed=42)
    phi_path = out / f"{TOPOLOGY}_phi.json"
    assert phi_path.exists()
    assert (out / f"{TOPOLOGY}_invariants_manifest.json").exists()
    phi = json.loads(phi_path.read_text())
    assert phi["schema"] == "invariants/v1"
    assert phi["topology"] == TOPOLOGY
    assert m["all_ok"] in (True, False)
    statuses = {e["status"] for e in phi["states"].values()}
    assert statuses, f"{TOPOLOGY}: Φ has no states at all — real finding"
    assert statuses <= {"ok", "insufficient_data", "mining_error"}
    has_rules = any(len(e.get("rules") or []) > 0
                    for e in phi["states"].values())
    if not has_rules:
        pytest.xfail(
            f"{TOPOLOGY}: 0 mined rules across all states — surface finding "
            f"(sparse states or feature set), not a silent pass")


@skip_no_data
def test_labels_overlap_real_gfsm_states(tmp_path: Path):
    # Correctness guard for the positional fb_to_col ordering contract:
    # labels derived from real calibration data must substantially match
    # the real gfsm `states` keys. A mis-ordered zip yields labels that
    # almost never correspond to real composite states.
    fb_to_col, components, gfsm = _fb_to_col()
    gfsm_state_keys = set((gfsm.get("states") or {}).keys())
    ds = DATA / TOPOLOGY / "dataset"
    ds_cfg = yaml.safe_load(DS_MANIFEST.read_text()) or {}
    cal_files = (ds_cfg.get("files") or {}).get("calibration") or []
    assert cal_files, f"{TOPOLOGY}: no calibration files"
    df = pd.concat([pd.read_csv(ds / r) for r in cal_files],
                   ignore_index=True)
    labels = label_frame(df, components, fb_to_col)
    distinct = set(labels)
    assert distinct, f"{TOPOLOGY}: no labels produced"
    in_gfsm = sum(1 for s in labels if s in gfsm_state_keys)
    frac = in_gfsm / len(labels)
    # A correct pairing → the vast majority of observed composite states
    # are reachable gfsm states. Mis-ordering → ~0. Use a conservative
    # floor that still catches scrambling but tolerates legitimate gfsm
    # BFS pruning of rarely-reached states.
    assert frac >= 0.5, (
        f"{TOPOLOGY}: only {frac:.1%} of calibration rows map to a known "
        f"gfsm state ({len(distinct)} distinct labels, "
        f"{len(distinct & gfsm_state_keys)} valid). Likely fb_to_col "
        f"ordering mismatch vs gfsm component order — REAL finding.")


@skip_no_data
def test_phi_deterministic(tmp_path: Path):
    fb_to_col, _c, _g = _fb_to_col()
    a = tmp_path / "a"
    b = tmp_path / "b"
    for o in (a, b):
        mine_topology(topology=TOPOLOGY, data_root=DATA, gfsm_dir=GFSM_DIR,
                      out_dir=o, fb_to_col=fb_to_col, min_observations=50,
                      max_evals=400, seed=42)
    pa = json.loads((a / f"{TOPOLOGY}_phi.json").read_text())
    pb = json.loads((b / f"{TOPOLOGY}_phi.json").read_text())
    pa.pop("generated_at", None)
    pb.pop("generated_at", None)
    assert pa == pb, f"{TOPOLOGY}: Φ not deterministic across seeded runs"
