"""Stage-3 STL calibration (faithful port of HydraulicSTLMonitor.calibrate + deduped pooled MB)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


def calibrate(profile, df):
    p = {'mb': {}, 'mb_window': {}, 'tank': {}, 'pump': {}, 'valve': {},
         'head': {}, 'pressure': {}, 'pslew': {}, 'symmetry': {}}

    for tk, feeders in profile.feeder_map.items():
        if tk not in df.columns:
            continue
        feeders = [f for f in feeders if f in df.columns]
        h = df[tk].values
        dh = h[1:] - h[:-1]
        qin = df[feeders].values[1:].sum(axis=1) if feeders else np.zeros(len(dh))
        X = qin.reshape(-1, 1)
        reg = LinearRegression().fit(X, dh)
        resid = dh - reg.predict(X)
        p['mb'][tk] = {
            'alpha': float(reg.coef_[0]),
            'offset': float(reg.intercept_),
            'eps': float(np.percentile(np.abs(resid), profile.mb_percentile) * profile.mb_safety + 0.005),
            'r2': float(reg.score(X, dh)),
            'feeders': feeders,
        }
        qin_full = df[feeders].values.sum(axis=1) if feeders else np.zeros(len(h))
        r1h = np.zeros(len(h))
        r1h[1:] = (h[1:] - h[:-1]) - p['mb'][tk]['alpha'] * qin_full[1:] - p['mb'][tk]['offset']
        for w in profile.mb_windows:
            rolled = pd.Series(r1h).rolling(w, min_periods=w).sum().dropna().values
            if len(rolled) > 100:
                eps_w = float(np.percentile(np.abs(rolled), profile.mb_window_percentile) * profile.mb_window_safety + 0.01)
                p['mb_window'].setdefault(tk, {})[f'w{w}'] = {'eps': eps_w}

    for tk in profile.tanks:
        if tk not in df.columns:
            continue
        h = df[tk].values
        dh = np.diff(h)
        phys = profile.tank_physical.get(tk, {'min': -1e9, 'max': 1e9})
        p['tank'][tk] = {
            'h_min': max(phys['min'], float(h.min() - profile.margin)),
            'h_max': min(phys['max'], float(h.max() + profile.margin)),
            'slew_max': float(np.percentile(np.abs(dh), profile.slew_percentile) * profile.slew_safety + 0.02),
        }

    for pid in profile.pumps:
        sc, fc = profile.pump_status_fmt.format(pid=pid), profile.pump_flow_fmt.format(pid=pid)
        if sc not in df.columns:
            continue
        if fc not in df.columns:
            frac = float((df[sc] > 0.5).mean())
            p['pump'][pid] = {'mode': 'status_only', 'on_fraction': frac}
            continue
        on = df.loc[df[sc] > 0.5, fc].values
        off = df.loc[df[sc] <= 0.5, fc].values
        frac = float((df[sc] > 0.5).mean())
        foff = float(np.percentile(np.abs(off), profile.pump_percentile) + 0.5) if len(off) > 5 else 0.5
        if frac < 0.005:
            p['pump'][pid] = {'mode': 'always_off', 'f_off_max': foff}
        elif frac > 0.995:
            p['pump'][pid] = {
                'mode': 'always_on',
                'f_on_min': float(np.percentile(on, 100 - profile.pump_percentile) - 1.0),
                'f_on_max': float(np.percentile(on, profile.pump_percentile) + 1.0),
                'f_off_max': foff,
            }
        else:
            p['pump'][pid] = {
                'mode': 'varying',
                'f_on_min': float(np.percentile(on, 100 - profile.pump_percentile) - 1.0) if len(on) else 0.0,
                'f_on_max': float(np.percentile(on, profile.pump_percentile) + 1.0) if len(on) else 0.0,
                'f_off_max': foff,
            }

    for vid, cols in profile.valves.items():
        sc, fc = cols['status'], cols['flow']
        if sc not in df.columns or fc not in df.columns:
            continue
        on = df.loc[df[sc] > 0.5, fc].values
        off = df.loc[df[sc] <= 0.5, fc].values
        p['valve'][vid] = {
            'status': sc,
            'flow': fc,
            'f_on_min': float(np.percentile(on, 100 - profile.pump_percentile) - 1.0) if len(on) else 0.0,
            'f_on_max': float(np.percentile(on, profile.pump_percentile) + 1.0) if len(on) else 0.0,
            'f_off_max': float(np.percentile(np.abs(off), profile.pump_percentile) + 0.5) if len(off) else 0.5,
        }

    for pid, (pdn, pup) in profile.pump_pressure_pairs.items():
        sc = profile.pump_status_fmt.format(pid=pid)
        if pdn not in df.columns or pup not in df.columns or sc not in df.columns:
            continue
        m = df[sc] > 0.5
        if m.sum() > 100:
            head = (df.loc[m, pdn] - df.loc[m, pup]).values
            p['head'][pid] = {
                'h_min': float(np.percentile(head, 0.5) - 2.0),
                'h_max': float(np.percentile(head, 99.5) + 2.0),
            }

    for j in profile.junctions:
        if j not in df.columns:
            continue
        v = df[j].values
        p['pressure'][j] = {
            'p_min': float(np.percentile(v, profile.pressure_low_pct) - 1.0),
            'p_max': float(np.percentile(v, profile.pressure_high_pct) + 1.0),
        }
        dv = np.abs(np.diff(v))
        p['pslew'][j] = {
            'slew_max': float(np.percentile(dv, profile.pslew_percentile) * profile.pslew_safety + 0.5),
        }

    for c1, c2 in profile.symmetry_pairs:
        if c1 not in df.columns or c2 not in df.columns:
            continue
        diff = np.abs(df[c1].values - df[c2].values)
        diff = diff[~np.isnan(diff)]
        if len(diff) < 100:
            continue
        thr = float(np.percentile(diff, profile.symmetry_percentile) * profile.symmetry_safety + 0.05)
        p['symmetry'][f'{c1}_{c2}'] = {'col1': c1, 'col2': c2, 'threshold': thr}

    return p


def calibrate_mb_pooled(profile, frames):
    feeder_map = profile.feeder_map
    mb_windows = profile.mb_windows
    mb_pct = profile.mb_percentile
    mb_safety = profile.mb_safety
    mbw_pct = profile.mb_window_percentile
    mbw_safety = profile.mb_window_safety
    scenario_frames = frames

    mb_params = {}
    mbw_params = {}
    for tk, feeders in feeder_map.items():
        all_dh, all_qin = [], []
        for df in scenario_frames:
            if tk not in df.columns:
                continue
            fs = [f for f in feeders if f in df.columns]
            if not fs:
                continue
            h = df[tk].values
            dh = h[1:] - h[:-1]
            qin = df[fs].values[1:].sum(axis=1)
            mask = np.isfinite(dh) & np.isfinite(qin)
            all_dh.append(dh[mask])
            all_qin.append(qin[mask])
        if not all_dh:
            continue
        dh_pool = np.concatenate(all_dh)
        qin_pool = np.concatenate(all_qin)
        if len(dh_pool) < 100:
            continue
        X = qin_pool.reshape(-1, 1)
        reg = LinearRegression().fit(X, dh_pool)
        resid = dh_pool - reg.predict(X)
        mb_params[tk] = {
            'alpha': float(reg.coef_[0]),
            'offset': float(reg.intercept_),
            'eps': float(np.percentile(np.abs(resid), mb_pct) * mb_safety + 0.005),
            'r2': float(reg.score(X, dh_pool)),
            'feeders': list(feeders),
        }
        all_rolled = {w: [] for w in mb_windows}
        for df in scenario_frames:
            if tk not in df.columns:
                continue
            fs = [f for f in feeders if f in df.columns]
            if not fs:
                continue
            h = df[tk].values
            qin_full = df[fs].values.sum(axis=1)
            r1h = np.zeros(len(h))
            r1h[1:] = (h[1:] - h[:-1]) - mb_params[tk]['alpha'] * qin_full[1:] - mb_params[tk]['offset']
            for w in mb_windows:
                rolled = pd.Series(r1h).rolling(w, min_periods=w).sum().dropna().values
                if len(rolled):
                    all_rolled[w].append(rolled)
        mbw_params[tk] = {}
        for w in mb_windows:
            if not all_rolled[w]:
                continue
            pool = np.concatenate(all_rolled[w])
            if len(pool) < 100:
                continue
            eps_w = float(np.percentile(np.abs(pool), mbw_pct) * mbw_safety + 0.01)
            mbw_params[tk][f'w{w}'] = {'eps': eps_w}
    return mb_params, mbw_params


def calibrate_topology(profile, dataset) -> dict:
    """Single-frame calibrate on the concatenated calibration frames; pooled
    mass-balance over the per-frame list when the profile has a feeder_map."""
    frames = dataset.calibration_frames
    cal_df = pd.concat(frames, ignore_index=True)
    params = calibrate(profile, cal_df)
    if profile.feeder_map:
        mb, mbw = calibrate_mb_pooled(profile, frames)
        params["mb"], params["mb_window"] = mb, mbw
    return params
