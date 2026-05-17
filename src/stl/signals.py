"""Stage-3 derived-signal construction (faithful port of HydraulicSTLMonitor.build_signals)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def build_signals(profile, df, p) -> dict:
    sig = {'time': list(range(len(df)))}
    for c in df.columns:
        if c in ('DATETIME', 'ATT_FLAG'):
            continue
        sig[c] = df[c].astype(float).tolist()
    for tk in profile.tanks:
        if tk not in df.columns:
            continue
        v = df[tk].astype(float).values
        d = np.zeros(len(v))
        d[1:] = v[1:] - v[:-1]
        sig[f'd{tk}'] = d.tolist()
    for j in profile.junctions:
        if j not in df.columns:
            continue
        v = df[j].astype(float).values
        d = np.zeros(len(v))
        d[1:] = v[1:] - v[:-1]
        sig[f'd{j}'] = d.tolist()
    for tk, mb in p['mb'].items():
        v = df[tk].astype(float).values
        dh = np.zeros(len(v))
        dh[1:] = v[1:] - v[:-1]
        qin = df[mb['feeders']].values.sum(axis=1) if mb['feeders'] else np.zeros(len(v))
        r = dh - mb['alpha'] * qin - mb['offset']
        sig[f'MB_RESID_{tk}'] = r.tolist()
        for wk in p['mb_window'].get(tk, {}):
            w = int(wk.lstrip('w'))
            rolled = pd.Series(r).rolling(w, min_periods=1).sum().fillna(0.0).values
            sig[f'MB_ROLL_{tk}_{wk}'] = rolled.tolist()
    for pid, (pdn, pup) in profile.pump_pressure_pairs.items():
        if pdn in df.columns and pup in df.columns:
            sig[f'HEAD_PU{pid}'] = (df[pdn].values - df[pup].values).tolist()
    return sig
