"""Stage-3 STL model: declarative TopologyProfile + error type."""

from __future__ import annotations

from dataclasses import dataclass


class StlError(Exception):
    """Unrecoverable Stage-3 error."""


@dataclass(frozen=True)
class TopologyProfile:
    name: str
    tanks: list[str]
    pumps: list
    valves: dict
    junctions: list[str]
    tank_physical: dict
    feeder_map: dict
    pump_pressure_pairs: dict
    control_rules: list
    symmetry_pairs: list
    state_vars: list[str]
    pump_status_fmt: str
    pump_flow_fmt: str
    mb_percentile: float = 99.0
    mb_safety: float = 1.10
    mb_window_percentile: float = 99.5
    mb_window_safety: float = 1.05
    slew_percentile: float = 99.5
    slew_safety: float = 1.20
    pump_percentile: float = 99.5
    pslew_percentile: float = 99.5
    pslew_safety: float = 1.20
    symmetry_percentile: float = 99.5
    symmetry_safety: float = 1.20
    pressure_low_pct: float = 0.05
    pressure_high_pct: float = 99.95
    hysteresis: int = 2
    margin: float = 0.05
    mb_windows: tuple = (3, 6, 12, 24)
    smoothing_window: int = 5
    min_fire_count: int = 1
