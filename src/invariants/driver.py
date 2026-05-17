"""Stage-invariants driver: orchestrate Φ mining for one topology."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .manifest import build_manifest
from .mine import MinerConfig, mine_state
from .model import InvariantsError, MinedRule
from .state_label import label_frame, load_gfsm_components


def _load_gfsm_json(gfsm_dir: Path, topology: str) -> dict[str, Any]:
    p = gfsm_dir / f"{topology}.gfsm.json"
    if not p.exists():
        raise InvariantsError(f"gfsm json not found: {p}")
    return json.loads(p.read_text())


def _load_gfsm_manifest(gfsm_dir: Path, topology: str) -> tuple[str, str]:
    p = gfsm_dir / f"{topology}_gfsm_manifest.json"
    if not p.exists():
        raise InvariantsError(f"gfsm manifest not found: {p}")
    return p.read_text(), p.name


def _load_calibration(
    data_root: Path, topology: str
) -> tuple[pd.DataFrame, str, str]:
    ds = data_root / topology / "dataset"
    man = ds / "dataset_manifest.yaml"
    if not man.exists():
        raise InvariantsError(f"dataset manifest not found: {man}")
    man_text = man.read_text()
    cfg = yaml.safe_load(man_text) or {}
    cal_files = (cfg.get("files") or {}).get("calibration") or []
    if not cal_files:
        raise InvariantsError(f"{topology}: no calibration files listed")
    frames = [pd.read_csv(ds / rel) for rel in cal_files]
    df = pd.concat(frames, ignore_index=True)
    return df, man_text, man.name


def mine_topology(
    *,
    topology: str,
    data_root: Path,
    gfsm_dir: Path,
    out_dir: Path,
    fb_to_col: dict[tuple[str, str], str],
    min_observations: int = 50,
    max_evals: int = 5000,
    seed: int = 42,
    feature_cols: list[str] | None = None,
    keep_going: bool = True,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    gfsm = _load_gfsm_json(Path(gfsm_dir), topology)
    gfsm_man_text, gfsm_man_name = _load_gfsm_manifest(
        Path(gfsm_dir), topology)
    cal_df, ds_man_text, ds_man_name = _load_calibration(
        Path(data_root), topology)

    components = load_gfsm_components(gfsm)
    labels = label_frame(cal_df, components, fb_to_col)

    if feature_cols is None:
        skip = set(fb_to_col.values())
        numeric = cal_df.select_dtypes(include="number").columns
        feature_cols = [c for c in numeric if c not in skip]

    cfg = MinerConfig(max_evals=max_evals, seed=seed)
    states: dict[str, dict[str, Any]] = {}
    states_summary: dict[str, dict[str, Any]] = {}
    all_ok = True

    for state_id in sorted(set(labels)):
        slice_df = cal_df.loc[labels == state_id]
        nobs = int(len(slice_df))
        if nobs < min_observations:
            states[state_id] = {"observations": nobs,
                                "status": "insufficient_data", "rules": []}
            states_summary[state_id] = {"observations": nobs, "rules": 0,
                                        "status": "insufficient_data"}
            continue
        try:
            rules: list[MinedRule] = mine_state(slice_df, feature_cols, cfg)
            states[state_id] = {"observations": nobs, "status": "ok",
                                "rules": [r.to_dict() for r in rules]}
            states_summary[state_id] = {"observations": nobs,
                                        "rules": len(rules), "status": "ok"}
        except Exception as exc:  # noqa: BLE001 - mining is best-effort
            all_ok = False
            states[state_id] = {"observations": nobs,
                                "status": "mining_error",
                                "errors": [repr(exc)], "rules": []}
            states_summary[state_id] = {"observations": nobs, "rules": 0,
                                        "status": "mining_error"}
            if not keep_going:
                break

    manifest = build_manifest(
        topology=topology,
        gfsm_manifest_name=gfsm_man_name, gfsm_manifest_text=gfsm_man_text,
        dataset_manifest_name=ds_man_name, dataset_manifest_text=ds_man_text,
        niaarm_cfg={"max_evals": max_evals, "confidence_min": 0.7,
                    "support_min": 0.1, "min_observations": min_observations,
                    "seed": seed, "algorithm": "ParticleSwarmAlgorithm"},
        states_summary=states_summary,
        all_ok=all_ok,
    )
    phi = {
        "schema": "invariants/v1",
        "topology": topology,
        "gfsm_manifest": gfsm_man_name,
        "gfsm_manifest_sha256": manifest["gfsm_manifest_sha256"],
        "dataset_manifest": ds_man_name,
        "dataset_manifest_sha256": manifest["dataset_manifest_sha256"],
        "niaarm": manifest["niaarm"],
        "generated_at": manifest["generated_at"],
        "states": states,
    }
    (out_dir / f"{topology}_phi.json").write_text(
        json.dumps(phi, indent=2, sort_keys=True, default=str) + "\n"
    )
    (out_dir / f"{topology}_invariants_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n"
    )
    return manifest
