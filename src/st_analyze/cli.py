"""CLI entry point for st_analyze (Stage 2)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .driver import analyze_topology
from .model import StAnalyzeError


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="st-analyze",
        description="Analyze st_gen-generated IEC 61131-3 ST into "
        "AST/PDG/invariant artifacts (pipeline Stage 2).",
    )
    p.add_argument(
        "--generated-dir",
        type=Path,
        default=Path("data/generated"),
        help="directory containing <topology>/ subdirs (default: data/generated)",
    )
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--topology", help="single topology to analyze")
    grp.add_argument(
        "--all",
        action="store_true",
        help="analyze every topology that has a <topology>_manifest.json",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output dir (default: <generated-dir>/<topology>/analysis)",
    )
    p.add_argument(
        "--keep-going",
        action="store_true",
        help="continue past a failing PLC instead of stopping",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def _discover_topologies(generated_dir: Path) -> list[str]:
    found = []
    for sub in sorted(generated_dir.iterdir()):
        if sub.is_dir() and (sub / f"{sub.name}_manifest.json").exists():
            found.append(sub.name)
    return found


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.all:
        topologies = _discover_topologies(args.generated_dir)
        if not topologies:
            print(
                f"error: no topologies with a manifest under "
                f"{args.generated_dir}",
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
                out_dir=args.out if not args.all else None,
                keep_going=args.keep_going,
            )
        except StAnalyzeError as exc:
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
