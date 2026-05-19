"""Φ-bound anomaly detector.

Loads the persisted Φ JSON (built by `invariants-mine`) and flags a row
when its composite-state is absent from Φ, OR when the number of violated
Φ rules for that state (antecedent holds but consequent fails) is at least
K. K is read from the Φ field `violation_threshold` (auto-calibrated by
`invariants-mine` from a clean false-positive budget); a legacy Φ without
the field defaults to K=1, i.e. flag on any single violation. Build-once /
reuse-many: `fit` deserializes Φ and verifies it is not stale vs the
current gfsm + dataset manifests (sha256).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from invariants.model import InvariantsError
from invariants.rule_eval import all_hold as _all_hold
from invariants.rule_eval import atom_holds as _atom_holds
from invariants.rule_eval import row_violation_count as _row_violation_count
from invariants.state_label import label_frame

from .model import MonitorError
from .protocol import StepFlags


class InvariantsAnomalyDetector:
    name = "invariants"

    def __init__(
        self,
        *,
        invariants_dir: Path,
        gfsm_dir: Path,
        data_root: Path,
        topology: str,
        components: list[tuple[str, str]],
        fb_to_col: dict[tuple[str, str], str],
    ):
        self._dir = Path(invariants_dir)
        self._gfsm_dir = Path(gfsm_dir)
        self._data_root = Path(data_root)
        self._topology = topology
        self._components = components
        self._fb_to_col = fb_to_col
        self._phi: dict[str, list[dict[str, Any]]] = {}
        self._k: int = 1

    def fit(self, calibration_frames: list[pd.DataFrame]
            ) -> "InvariantsAnomalyDetector":
        path = self._dir / f"{self._topology}_phi.json"
        if not path.exists():
            raise MonitorError(f"phi json not found: {path}")
        data = json.loads(path.read_text())
        # Staleness: Φ recorded the gfsm manifest sha256 it was mined
        # against; if the current gfsm manifest differs, Φ is stale.
        recorded = data.get("gfsm_manifest_sha256")
        gman = self._gfsm_dir / f"{self._topology}_gfsm_manifest.json"
        if recorded is not None and gman.exists():
            actual = hashlib.sha256(
                gman.read_text().encode("utf-8")).hexdigest()
            if recorded != actual:
                raise MonitorError(
                    "stale Φ artifact (gfsm manifest sha mismatch); "
                    "re-run invariants-mine"
                )
        recorded_ds = data.get("dataset_manifest_sha256")
        dsman = (self._data_root / self._topology / "dataset"
                 / "dataset_manifest.yaml")
        if recorded_ds is not None and dsman.exists():
            actual_ds = hashlib.sha256(
                dsman.read_text().encode("utf-8")).hexdigest()
            if recorded_ds != actual_ds:
                raise MonitorError(
                    "stale Φ artifact (dataset manifest sha mismatch); "
                    "re-run invariants-mine"
                )
        self._k = max(1, int(data.get("violation_threshold", 1)))
        self._phi = {
            s: (e.get("rules") or [])
            for s, e in (data.get("states") or {}).items()
        }
        for state_id, rules in self._phi.items():
            for r in rules:
                for atom in (r.get("antecedent", [])
                             + r.get("consequent", [])):
                    if atom.get("op") == "in":
                        v = atom.get("val")
                        if not (isinstance(v, list) and len(v) == 2):
                            raise MonitorError(
                                f"malformed Φ rule in state {state_id!r}: "
                                f"'in' atom requires a 2-element val, "
                                f"got {v!r}"
                            )
        return self

    def predict(self, frame: pd.DataFrame) -> StepFlags:
        try:
            labels = label_frame(frame, self._components, self._fb_to_col)
        except InvariantsError as exc:
            raise MonitorError(str(exc)) from exc
        flags = np.zeros(len(frame), dtype=int)
        for i, s in enumerate(labels):
            rules = self._phi.get(s)
            if rules is None:
                flags[i] = 1  # composite state absent from Φ
                continue
            if not rules:
                continue
            # Full count needed: cannot short-circuit on first violation
            # when K>1 (legacy K=1 still flags on the first).
            if _row_violation_count(frame.iloc[i], rules) >= self._k:
                flags[i] = 1
        return StepFlags(flags=flags, scores=flags.astype(float))
