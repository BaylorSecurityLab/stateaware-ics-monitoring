"""CLI entry point for gfsm-build (Stage 4). Mirrors st_analyze/cli.py."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .driver import analyze_topology
from .model import GfsmError


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gfsm-build",
        description="Compose per-PLC local FSMs into a global FSM "
        "(pipeline Stage 4).",
    )
    p.add_argument(
        "--generated-dir",
        type=Path,
        default=Path("data/generated"),
        help="directory containing <topology>/ subdirs "
        "(default: data/generated)",
    )
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--topology", help="single topology to build")
    grp.add_argument(
        "--all",
        action="store_true",
        help="build every topology with a "
        "<topology>_analysis_manifest.json",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="output dir (default: <generated-dir>/<topology>/gfsm)",
    )
    p.add_argument(
        "--max-states",
        type=int,
        default=100_000,
        help="hard cap on global states (default: 100000)",
    )
    p.add_argument(
        "--jobs",
        type=int,
        default=None,
        help="parallel workers (default: min(cpu, units); 1 = sequential)",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def _discover_topologies(generated_dir: Path) -> list[str]:
    found: list[str] = []
    if not generated_dir.is_dir():
        return found
    for sub in sorted(generated_dir.iterdir()):
        manifest = (
            sub / "analysis" / f"{sub.name}_analysis_manifest.json"
        )
        if sub.is_dir() and manifest.exists():
            found.append(sub.name)
    return found


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.all:
        topologies = _discover_topologies(args.generated_dir)
        if not topologies:
            print(
                f"error: no topologies with a Stage 2 analysis manifest "
                f"under {args.generated_dir}",
                file=sys.stderr,
            )
            return 2
    else:
        topologies = [args.topology]

    overall_ok = True
    had_error = False
    for topology in topologies:
        try:
            manifest = analyze_topology(
                generated_dir=args.generated_dir,
                topology=topology,
                out_dir=args.out_dir if not args.all else None,
                max_states=args.max_states,
                jobs=args.jobs,
            )
        except GfsmError as exc:
            print(f"error: {exc}", file=sys.stderr)
            if not args.all:
                return 2
            had_error = True
            continue

        if not manifest.get("all_ok", True):
            overall_ok = False
        if args.verbose:
            print(
                f"{topology}: {len(manifest['plcs'])} PLCs, "
                f"all_ok={manifest.get('all_ok')}",
                file=sys.stderr,
            )
            print(json.dumps(manifest, indent=2))

    if had_error:
        return 2
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
