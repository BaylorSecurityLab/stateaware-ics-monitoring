"""CLI entry point for st_gen."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import emit, load_plcs, parse_inp
from .model import StGenError


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="st-gen",
        description="Generate IEC 61131-3 Structured Text (CASE) from EPANET INP + plcs.yaml.",
    )
    p.add_argument("--inp", required=True, type=Path, help="EPANET .inp file")
    p.add_argument("--plcs", required=True, type=Path, help="DHALSIM-style plcs.yaml")
    p.add_argument("--out", required=True, type=Path, help="output directory")
    p.add_argument(
        "--topology",
        default=None,
        help="topology name (default: --inp basename without extension)",
    )
    p.add_argument(
        "--no-manifest",
        action="store_true",
        help="skip writing <topology>_manifest.json",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    topology = args.topology or args.inp.stem
    try:
        network = parse_inp(args.inp)
        plcs = load_plcs(args.plcs)
        emit(
            network=network,
            plcs=plcs,
            out_dir=args.out,
            topology=topology,
            write_manifest=not args.no_manifest,
            inp_filename=args.inp.name,
            plcs_filename=args.plcs.name,
        )
    except StGenError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.verbose:
        print(f"wrote {len(plcs)} ST files to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
