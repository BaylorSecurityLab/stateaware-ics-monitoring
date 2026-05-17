"""Pure ltown zarr-layout / tank-detection helpers (no zarr dependency)."""
from __future__ import annotations

import re

import numpy as np

TANK_ELEVATION_M = 98.68
TANK_MAX_LEVEL_M = 4.0
N_TIMESTEPS = 24


def parse_inp(path):
    text = path.read_text(errors='replace')
    out = {}
    for sec in ('JUNCTIONS', 'RESERVOIRS', 'TANKS', 'PIPES', 'PUMPS', 'VALVES'):
        m = re.search(rf'\[{sec}\](.*?)(?=^\[|\Z)', text, re.DOTALL | re.MULTILINE)
        rows = []
        if m:
            for line in m.group(1).split('\n'):
                line = line.strip()
                if not line or line.startswith(';;'):
                    continue
                parts = line.split(';', 1)
                data = parts[0].strip().split()
                comment = parts[1].strip() if len(parts) > 1 else ''
                if data:
                    rows.append({'name': data[0], 'comment': comment})
        out[sec] = rows
    return out


def reshape_to_time_axis(flat_sim, n_axis, n_t, layout):
    if layout == 'time_axis':
        return flat_sim.reshape(n_t, n_axis)
    return flat_sim.reshape(n_axis, n_t).T


def detect_layout(head_arr, n_nodes, n_t, n_sims_probe=10,
                  tank_elevation_m=TANK_ELEVATION_M,
                  tank_max_level_m=TANK_MAX_LEVEL_M):
    results = {}
    for layout in ('axis_time', 'time_axis'):
        cand = {}
        for s in range(min(n_sims_probe, head_arr.shape[0])):
            grid = reshape_to_time_axis(head_arr[s], n_nodes, n_t, layout)
            late = grid[1:]
            mn = late.min(axis=0)
            mx = late.max(axis=0)
            in_range = (mn >= tank_elevation_m - 0.2) & (mx <= tank_elevation_m + tank_max_level_m + 0.2)
            for n in np.where(in_range)[0]:
                cand[n] = cand.get(n, 0) + 1
        if cand:
            top, count = max(cand.items(), key=lambda kv: kv[1])
            results[layout] = (int(top), int(count))
    if not results:
        return None, None
    best = max(results, key=lambda k: results[k][1])
    if results[best][1] < n_sims_probe // 2:
        return None, None
    return best, results[best][0]


def find_tank_index(head_arr, n_nodes, layout, n_sims_probe=10,
                    tank_elevation_m=TANK_ELEVATION_M,
                    tank_max_level_m=TANK_MAX_LEVEL_M):
    candidate_freq = np.zeros(n_nodes, dtype=int)
    sample_means = {n: [] for n in range(n_nodes)}
    for s in range(min(n_sims_probe, head_arr.shape[0])):
        grid = reshape_to_time_axis(head_arr[s], n_nodes, N_TIMESTEPS, layout)
        late = grid[1:]
        node_min = late.min(axis=0)
        node_max = late.max(axis=0)
        in_range = (node_min >= tank_elevation_m - 0.2) & (node_max <= tank_elevation_m + tank_max_level_m + 0.2)
        for n in np.where(in_range)[0]:
            candidate_freq[n] += 1
            sample_means[n].append(float(late[:, n].mean()))
    if candidate_freq.max() < n_sims_probe // 2:
        return None, []
    top = int(np.argmax(candidate_freq))
    diagnostics = []
    for n in np.argsort(-candidate_freq)[:8]:
        if candidate_freq[n] > 0:
            diagnostics.append((int(n), int(candidate_freq[n]), float(np.mean(sample_means[n]))))
    return top, diagnostics


def find_reservoir_indices(head_arr, n_nodes, tank_idx, layout, n_sims_probe=10):
    all_const = np.ones(n_nodes, dtype=bool)
    sample_mean = np.zeros(n_nodes)
    for s in range(min(n_sims_probe, head_arr.shape[0])):
        grid = reshape_to_time_axis(head_arr[s], n_nodes, N_TIMESTEPS, layout)
        late = grid[1:]
        std = late.std(axis=0)
        all_const &= (std < 1e-5)
        if s == 0:
            sample_mean = late.mean(axis=0)
    if tank_idx is not None:
        all_const[tank_idx] = False
    idxs = sorted(np.where(all_const)[0].tolist())
    return idxs, [(int(n), float(sample_mean[n])) for n in idxs]
