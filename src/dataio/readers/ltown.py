"""ltown raw zarr simgen -> normalized calibration + held-out-normal eval (port of l_town_detect.py)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..model import DataIoError
from ..schema import canonicalize_columns
from .ltown_layout import parse_inp, reshape_to_time_axis, detect_layout, find_tank_index

SOURCE_NAME = "simgen_L-TOWN_Real_20240403_1905.zip"
TANK_ELEVATION_M = 98.68
TANK_NAME = "T1"
PUMP_NAME = "PUMP_1"
N_TIMESTEPS = 24
N_CAL_SIMS = 800
N_VAL_SIMS = 200


def _extract_sim(p_arr, h_arr, f_arr, sim_idx, sensor_idx, tank_idx, pump_link_idx,
                 n_nodes, n_links, layout, tank_elevation_m=TANK_ELEVATION_M):
    p_sim = reshape_to_time_axis(p_arr[sim_idx], n_nodes, N_TIMESTEPS, layout)
    h_sim = reshape_to_time_axis(h_arr[sim_idx], n_nodes, N_TIMESTEPS, layout)
    f_sim = reshape_to_time_axis(f_arr[sim_idx], n_links, N_TIMESTEPS, layout)
    df = pd.DataFrame({
        'iteration': np.arange(N_TIMESTEPS) + sim_idx * N_TIMESTEPS,
        't_local': np.arange(N_TIMESTEPS),
        TANK_NAME: h_sim[:, tank_idx] - tank_elevation_m,
        f'F_{PUMP_NAME}': np.abs(f_sim[:, pump_link_idx]),
    })
    df[PUMP_NAME] = (df[f'F_{PUMP_NAME}'] > 1e-4).astype(float)
    for j_name, j_idx in sensor_idx.items():
        df[j_name] = p_sim[:, j_idx]
    return df.iloc[1:].reset_index(drop=True)


def build_normalized(raw_root: Path):
    """Return (calibration_frames, eval_named, column_map, source_name).

    Raw zarr source: <raw_root>/'L Town'/'simgen_L-TOWN_Real_20240403_1905.zip'
    Topology .inp:   <raw_root>/'L Town'/'L-TOWN.inp'
    """
    import zarr  # noqa: PLC0415 — lazy import; module must not require zarr at import time
    import zarr.storage  # noqa: PLC0415 — zarr>=3 moved ZipStore to zarr.storage

    raw_root = Path(raw_root)
    ltown_dir = raw_root / "L Town"
    simgen_zip = ltown_dir / SOURCE_NAME
    inp_path = ltown_dir / "L-TOWN.inp"

    if not simgen_zip.exists():
        raise DataIoError(f"L-TOWN simgen zip not found: {simgen_zip}")
    if not inp_path.exists():
        raise DataIoError(f"L-TOWN .inp not found: {inp_path}")

    store = zarr.storage.ZipStore(str(simgen_zip), mode='r')
    root = zarr.open(store=store, mode='r')
    pressure_arr = root['pressure']
    head_arr = root['head']
    flow_arr = root['flowrate']

    # Tank elevation / max level are authoritative in the archive itself;
    # do not hardcode (different simgens use different tanks).
    tank_elev = float(np.asarray(root['tank_elevation']).flat[0])
    tank_maxl = float(np.asarray(root['tank_max_level']).flat[0])

    sec = parse_inp(inp_path)
    n_j = len(sec['JUNCTIONS'])
    n_r = len(sec['RESERVOIRS'])
    n_tk = len(sec['TANKS'])
    n_pi = len(sec['PIPES'])
    n_v = len(sec['VALVES'])
    n_pu = len(sec['PUMPS'])
    n_nodes = n_j + n_r + n_tk
    n_links = n_pi + n_v + n_pu

    layout, _ = detect_layout(head_arr, n_nodes, N_TIMESTEPS,
                              tank_elevation_m=tank_elev,
                              tank_max_level_m=tank_maxl)
    if layout is None:
        raise DataIoError("L-TOWN: could not detect zarr layout (axis_time vs time_axis)")

    tank_idx, _ = find_tank_index(head_arr, n_nodes, layout,
                                  tank_elevation_m=tank_elev,
                                  tank_max_level_m=tank_maxl)
    if tank_idx is None:
        tank_idx = n_j  # fallback: first node after junctions

    pump_link_idx = n_pi + n_v

    sensor_idx = {
        j['name']: i
        for i, j in enumerate(sec['JUNCTIONS'])
        if 'PRESSURE SENSOR' in j['comment'].upper()
    }

    n_sims_total = pressure_arr.shape[0]
    n_cal = min(N_CAL_SIMS, n_sims_total - N_VAL_SIMS)

    # Build calibration frames — canonicalize each
    calibration_frames: list[pd.DataFrame] = []
    column_map: dict[str, str] = {}
    for i in range(n_cal):
        raw_df = _extract_sim(
            pressure_arr, head_arr, flow_arr,
            i, sensor_idx, tank_idx, pump_link_idx,
            n_nodes, n_links, layout, tank_elev,
        )
        if i == 0:
            # Capture column_map from first sim's raw columns before rename
            column_map = canonicalize_columns(list(raw_df.columns))
        raw_df = raw_df.rename(columns=column_map)
        calibration_frames.append(raw_df)

    # Build validation frames — concat, add label=0 (int), canonicalize
    val_frames: list[pd.DataFrame] = []
    for i in range(n_cal, n_cal + N_VAL_SIMS):
        raw_df = _extract_sim(
            pressure_arr, head_arr, flow_arr,
            i, sensor_idx, tank_idx, pump_link_idx,
            n_nodes, n_links, layout, tank_elev,
        )
        raw_df = raw_df.rename(columns=column_map)
        val_frames.append(raw_df)

    val_df = pd.concat(val_frames, ignore_index=True)
    val_df['label'] = 0  # all-zero int labels (ltown has no labeled attacks)

    eval_named: list[tuple[str, pd.DataFrame]] = [("normal", val_df)]

    return calibration_frames, eval_named, column_map, SOURCE_NAME
