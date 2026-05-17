"""Parallel rtamt STL evaluation. Output is byte-identical regardless of jobs."""

from __future__ import annotations

from . import _rtamt_compat  # noqa: F401  # MUST precede any rtamt import

import os
import re
from concurrent.futures import ProcessPoolExecutor

import numpy as np

STL_RESERVED = {"and", "or", "not", "abs", "always", "eventually",
                "until", "implies"}


def vars_in(formula: str) -> list[str]:
    toks = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", formula)
    return sorted({t for t in toks if t not in STL_RESERVED})


def _eval_one(args: tuple[str, str, dict, int]):
    """Top-level picklable worker: build the rtamt spec INSIDE the worker."""
    from . import _rtamt_compat  # noqa: F401  # shim in spawn worker too
    import rtamt

    name, formula, feed, n = args
    used = [v for v in vars_in(formula) if v in feed]
    spec = rtamt.StlDiscreteTimeSpecification()
    for v in used:
        spec.declare_var(v, "float")
    spec.spec = formula
    try:
        spec.parse()
    except Exception:
        return name, np.zeros(n)
    try:
        res = spec.evaluate({"time": feed["time"], **{v: feed[v] for v in used}})
        arr = np.fromiter((row[1] for row in res), float, count=len(res))
        if len(arr) < n:
            pad = np.full(n - len(arr), arr[-1] if len(arr) else 0.0)
            arr = np.concatenate([arr, pad])
        return name, arr
    except Exception:
        return name, np.zeros(n)


def evaluate_stl_batch(specs: dict[str, str], signals: dict,
                       jobs: int | None = None) -> dict[str, np.ndarray]:
    n = len(signals["time"])
    items = sorted(specs.items())  # deterministic dispatch order
    payloads = []
    for name, formula in items:
        used = [v for v in vars_in(formula) if v in signals]
        feed = {"time": list(signals["time"])}
        for v in used:
            feed[v] = list(signals[v])
        payloads.append((name, formula, feed, n))

    if jobs is None:
        jobs = min(os.cpu_count() or 1, max(1, len(payloads)))

    if jobs <= 1 or len(payloads) <= 1:
        results = [_eval_one(p) for p in payloads]
    else:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            results = list(ex.map(_eval_one, payloads))

    # Re-assemble in sorted formula-name order -> byte-identical vs jobs.
    return {name: arr for name, arr in sorted(results, key=lambda kv: kv[0])}


def min_robustness(robustness: dict[str, np.ndarray], n: int):
    rmin = np.full(n, np.inf)
    arg = np.full(n, "", dtype=object)
    for name in sorted(robustness):
        arr = robustness[name]
        hit = arr < rmin
        rmin = np.minimum(rmin, arr)
        arg[hit] = name
    return rmin, arg
