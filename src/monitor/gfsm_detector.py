"""GFSM δ-conformance anomaly detector.

Loads the persisted GFSM JSON (built by `gfsm-build`) and flags rows whose
composite-state encoding is not a known state, or whose (prev -> curr)
transition is not in G's transition relation. Stutter (state -> same
state) is always permitted. Build-once / reuse-many: `fit` deserializes the
JSON; mining/extraction never happen at predict time.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from invariants.model import InvariantsError
from invariants.state_label import label_frame, load_gfsm_components

from .model import MonitorError
from .protocol import StepFlags


class GfsmAnomalyDetector:
    name = "gfsm"

    def __init__(
        self,
        *,
        gfsm_dir: Path,
        topology: str,
        fb_to_col: dict[tuple[str, str], str],
    ):
        self._gfsm_dir = Path(gfsm_dir)
        self._topology = topology
        self._fb_to_col = fb_to_col
        self._components: list[tuple[str, str]] = []
        self._known_states: set[str] = set()
        self._allowed: set[tuple[str, str]] = set()

    def fit(self, calibration_frames: list[pd.DataFrame]) -> "GfsmAnomalyDetector":
        path = self._gfsm_dir / f"{self._topology}.gfsm.json"
        if not path.exists():
            raise MonitorError(f"gfsm json not found: {path}")
        gfsm = json.loads(path.read_text())
        self._components = load_gfsm_components(gfsm)
        self._known_states = set((gfsm.get("states") or {}).keys())
        for t in gfsm.get("transitions") or []:
            frm = t.get("from_state", t.get("from"))
            to = t.get("to_state", t.get("to"))
            if frm is None or to is None:
                raise MonitorError(
                    f"gfsm transition missing from/to keys: {t!r}")
            self._allowed.add((frm, to))
        return self

    def predict(self, frame: pd.DataFrame) -> StepFlags:
        try:
            labels = label_frame(frame, self._components, self._fb_to_col)
        except InvariantsError as exc:
            raise MonitorError(str(exc)) from exc
        flags = np.zeros(len(frame), dtype=int)
        prev: str | None = None
        for i, s in enumerate(labels):
            unknown = s not in self._known_states
            if i == 0:
                flags[i] = int(unknown)
            elif unknown:
                flags[i] = 1
            elif s != prev and (prev, s) not in self._allowed:
                flags[i] = 1
            prev = s
        return StepFlags(flags=flags, scores=flags.astype(float))
