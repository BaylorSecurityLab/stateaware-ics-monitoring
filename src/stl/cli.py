"""CLI entry point for stl-monitor (Stage 3)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .driver import run_topology
from .model import StlError
from .profiles import PROFILES


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stl-monitor",
        description="Data-driven STL monitor (pipeline Stage 3).")
    p.add_argument("--data-root", type=Path, default=Path("data"))
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--topology", choices=sorted(PROFILES))
    grp.add_argument("--all", action="store_true")
    p.add_argument("--out", type=Path, default=None,
                   help="output dir (default: <data-root>/generated/<topo>/stl)")
    p.add_argument("--jobs", type=int, default=None)
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    topologies = sorted(PROFILES) if args.all else [args.topology]
    had_error = False
    overall_ok = True
    for topology in topologies:
        try:
            manifest = run_topology(
                topology=topology, data_root=args.data_root,
                out_dir=args.out if not args.all else None, jobs=args.jobs)
        except StlError as exc:
            print(f"error: {exc}", file=sys.stderr)
            if not args.all:
                return 2
            had_error = True
            continue
        if not manifest.get("all_ok", True):
            overall_ok = False
        if args.verbose:
            print(f"{topology}: {manifest['n_formulas']} formulas",
                  file=sys.stderr)
    if had_error:
        return 2
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
