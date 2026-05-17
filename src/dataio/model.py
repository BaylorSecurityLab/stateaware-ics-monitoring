"""Shared dataset model for Stage 3 STL and the future invariant quantifier."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


class DataIoError(Exception):
    """Unrecoverable dataset load/ingest error."""


@dataclass(frozen=True)
class DatasetSchema:
    topology: str
    tank_cols: list[str]
    pump_status_cols: list[str]
    pump_flow_cols: list[str]
    junction_cols: list[str]
    column_map: dict[str, str]


@dataclass
class Scenario:
    name: str
    frame: pd.DataFrame
    labels: np.ndarray
    attack_windows: list[tuple[str, str, str]] = field(default_factory=list)


@dataclass
class TopologyDataset:
    topology: str
    calibration_frames: list[pd.DataFrame]
    eval_scenarios: list[Scenario]
    schema: DatasetSchema
