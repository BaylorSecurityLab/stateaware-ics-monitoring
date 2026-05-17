"""Stage-3 STL synthesis (faithful port of HydraulicSTLMonitor.synthesize/write_formulas)."""

from __future__ import annotations

from pathlib import Path


def synthesize(profile, p) -> dict[str, str]:
    specs = {}
    for tk, mb in p['mb'].items():
        specs[f'MB_{tk}'] = f'abs(MB_RESID_{tk}) <= {mb["eps"]:.6f}'
    for tk, ws in p['mb_window'].items():
        for wk, info in ws.items():
            specs[f'MBW_{tk}_{wk}'] = f'abs(MB_ROLL_{tk}_{wk}) <= {info["eps"]:.6f}'
    for tk, tb in p['tank'].items():
        phys = profile.tank_physical.get(tk, {'min': -1e9, 'max': 1e9})
        specs[f'PHYS_{tk}'] = f'{tk} >= {phys["min"]:.4f} and {tk} <= {phys["max"]:.4f}'
        specs[f'RANGE_{tk}'] = f'{tk} >= {tb["h_min"]:.4f} and {tk} <= {tb["h_max"]:.4f}'
        specs[f'SLEW_{tk}'] = f'abs(d{tk}) <= {tb["slew_max"]:.4f}'
    for pid, info in p['pump'].items():
        sc, fc = profile.pump_status_fmt.format(pid=pid), profile.pump_flow_fmt.format(pid=pid)
        if info['mode'] == 'status_only':
            specs[f'PUMP_BINARY_{pid}'] = f'({sc} >= -0.1) and ({sc} <= 1.1)'
            continue
        if info['mode'] == 'always_off':
            specs[f'PUMP_DORMANT_{pid}'] = f'{sc} <= 0.5 and abs({fc}) <= {info["f_off_max"]:.4f}'
        elif info['mode'] == 'always_on':
            specs[f'PUMP_ACTIVE_{pid}'] = f'{sc} > 0.5 and {fc} >= {info["f_on_min"]:.4f} and {fc} <= {info["f_on_max"]:.4f}'
        else:
            specs[f'PUMP_ON_{pid}'] = f'({sc} <= 0.5) or ({fc} >= {info["f_on_min"]:.4f} and {fc} <= {info["f_on_max"]:.4f})'
            specs[f'PUMP_OFF_{pid}'] = f'({sc} > 0.5) or (abs({fc}) <= {info["f_off_max"]:.4f})'
    for vid, info in p['valve'].items():
        sc, fc = info['status'], info['flow']
        specs[f'VALVE_ON_{vid}'] = f'({sc} <= 0.5) or ({fc} >= {info["f_on_min"]:.4f} and {fc} <= {info["f_on_max"]:.4f})'
        specs[f'VALVE_OFF_{vid}'] = f'({sc} > 0.5) or (abs({fc}) <= {info["f_off_max"]:.4f})'
    for sc, tk, low, high in profile.control_rules:
        specs[f'CTRL_HI_{sc}_{tk}'] = f'({tk} <= {high + profile.margin:.4f}) or ({sc} <= 0.5)'
        specs[f'CTRL_LO_{sc}_{tk}'] = f'({tk} >= {low - profile.margin:.4f}) or ({sc} > 0.5)'
    for key, info in p.get('symmetry', {}).items():
        specs[f'SYMM_{key}'] = f'abs({info["col1"]} - {info["col2"]}) <= {info["threshold"]:.4f}'
    for pid, hp in p['head'].items():
        sc = profile.pump_status_fmt.format(pid=pid)
        specs[f'HEAD_PU{pid}'] = f'({sc} <= 0.5) or (HEAD_PU{pid} >= {hp["h_min"]:.4f} and HEAD_PU{pid} <= {hp["h_max"]:.4f})'
    for j, pp in p['pressure'].items():
        specs[f'PRESSURE_{j}'] = f'{j} >= {pp["p_min"]:.4f} and {j} <= {pp["p_max"]:.4f}'
    for j, sp in p['pslew'].items():
        specs[f'PSLEW_{j}'] = f'abs(d{j}) <= {sp["slew_max"]:.4f}'
    return specs


def write_formulas(specs, path) -> None:
    groups = {'MB_': [], 'MBW_': [], 'PHYS_': [], 'RANGE_': [], 'SLEW_': [],
              'PUMP_': [], 'VALVE_': [], 'HEAD_': [], 'PRESSURE_': [], 'PSLEW_': [],
              'CTRL_': [], 'SYMM_': []}
    for fn, formula in specs.items():
        for k in groups:
            if fn.startswith(k):
                groups[k].append((fn, formula))
                break
    with open(path, 'w') as fh:
        fh.write(f'STL Specifications ({len(specs)} total)\n')
        fh.write('=' * 80 + '\n\n')
        for g, items in groups.items():
            if not items:
                continue
            fh.write(f'-- {g.rstrip("_")} ({len(items)})\n')
            for fn, formula in items:
                fh.write(f'{fn}\n  always[ {formula} ]\n\n')
