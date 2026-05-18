"""CLI for the invariants stage."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .driver import mine_topology
from .model import InvariantsError
from .state_label import resolve_fb_to_col_from_paths


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="invariants-mine",
        description="Mine state-aware NiaARM invariants Φ per composite "
        "GFSM state.",
    )
    p.add_argument("--data-root", type=Path, default=Path("data"))
    p.add_argument("--gfsm-dir", type=Path, default=None,
                   help="override per-topology gfsm dir "
                   "(default: <data-root>/generated/<topology>/gfsm)")
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--topology")
    grp.add_argument("--all", action="store_true")
    p.add_argument("--out", type=Path, default=None,
                   help="output dir (default: "
                   "<data-root>/generated/<topo>/invariants)")
    p.add_argument("--min-observations", type=int, default=50)
    p.add_argument("--max-evals", type=int, default=5000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--strict", action="store_true",
                   help="fail immediately on any mining error")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def _gfsm_dir_for(topo: str, args: argparse.Namespace) -> Path:
    if args.gfsm_dir is not None:
        return args.gfsm_dir
    return args.data_root / "generated" / topo / "gfsm"


def _resolve_fb_to_col(
    topo: str, gfsm_dir: Path, data_root: Path
) -> dict[tuple[str, str], str]:
    fb_to_col, _components, _gfsm = resolve_fb_to_col_from_paths(
        gfsm_dir, topo, data_root)
    return fb_to_col


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.all:
        gen_root = args.data_root / "generated"
        topologies = (
            sorted(
                d.name
                for d in gen_root.iterdir()
                if d.is_dir()
                and not d.name.startswith((".", "_"))
                and (d / "gfsm" / f"{d.name}.gfsm.json").exists()
            )
            if gen_root.exists()
            else []
        )
        if not topologies:
            print(
                f"error: --all found no topologies with "
                f"<topo>/gfsm/<topo>.gfsm.json under {gen_root}",
                file=sys.stderr,
            )
            return 2
    else:
        topologies = [args.topology]

    overall_ok = True
    had_error = False
    for topo in topologies:
        gfsm_dir = _gfsm_dir_for(topo, args)
        if args.all:
            out = args.data_root / "generated" / topo / "invariants"
        else:
            out = args.out if args.out else (
                args.data_root / "generated" / topo / "invariants")
        try:
            fb_to_col = _resolve_fb_to_col(topo, gfsm_dir, args.data_root)
            manifest = mine_topology(
                topology=topo, data_root=args.data_root,
                gfsm_dir=gfsm_dir, out_dir=out,
                fb_to_col=fb_to_col,
                min_observations=args.min_observations,
                max_evals=args.max_evals, seed=args.seed,
                keep_going=not args.strict,
            )
        except InvariantsError as exc:
            print(f"error: {exc}", file=sys.stderr)
            if not args.all:
                return 2
            had_error = True
            continue
        if not manifest.get("all_ok", True):
            overall_ok = False
        if args.verbose:
            n = len(manifest.get("states") or {})
            print(f"{topo}: {n} states, all_ok={manifest.get('all_ok')}",
                  file=sys.stderr)

    if had_error:
        return 2
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
