"""Stage-3 detection metrics + hysteresis (faithful port of general_refactored_class helpers)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    matthews_corrcoef,
    average_precision_score,
    balanced_accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    roc_auc_score,
)


def hysteresis_filter(min_rob, k):
    n = len(min_rob)
    raw = (min_rob < 0).astype(int)
    confirmed = np.zeros(n, dtype=int)
    run = 0
    for i in range(n):
        run = run + 1 if raw[i] else 0
        if run >= k:
            confirmed[i - k + 1:i + 1] = 1
    return confirmed


def detection_metrics(y_true, y_pred, scores):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    out = {
        'precision': float(precision_score(y_true, y_pred, zero_division=0)),
        'recall': float(recall_score(y_true, y_pred, zero_division=0)),
        'f1': float(f1_score(y_true, y_pred, zero_division=0)),
        'mcc': float(matthews_corrcoef(y_true, y_pred)),
        'balanced_accuracy': float(balanced_accuracy_score(y_true, y_pred)),
        'tp': int(tp), 'fp': int(fp), 'tn': int(tn), 'fn': int(fn),
    }
    if len(np.unique(y_true)) > 1:
        out['aucpr'] = float(average_precision_score(y_true, scores))
        out['aucroc'] = float(roc_auc_score(y_true, scores))
    else:
        out['aucpr'] = float('nan')
        out['aucroc'] = float('nan')
    return out


# port of HydraulicSTLMonitor.per_attack_breakdown (self.datetime_format -> param):
def per_attack_breakdown(y_pred, dt, windows, datetime_format="%d/%m/%y %H"):
    rows = []
    for aid, s, e in windows:
        sp = pd.to_datetime(s, format=datetime_format)
        ep = pd.to_datetime(e, format=datetime_format)
        mask = ((dt >= sp) & (dt <= ep)).values
        total = int(mask.sum())
        hit = int(y_pred[mask].sum())
        within = np.where(y_pred[mask] == 1)[0]
        ttd = int(within[0]) if len(within) else None
        s_ttd = 1.0 - (ttd / total) if ttd is not None else 0.0
        rows.append({
            'attack': aid, 'window': f'{s} -> {e}',
            'duration_h': total, 'detected_steps': hit,
            'detection_rate': hit / max(total, 1),
            'time_to_detect_h': ttd, 'ttd_score': s_ttd,
        })
    return rows
