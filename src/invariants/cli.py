"""CLI for the invariants stage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from stl.model import StlError
from stl.profiles import get_profile

from .driver import mine_topology
from .model import InvariantsError
from .state_label import load_gfsm_components


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="invariants-mine",
        description="Mine state-aware NiaARM invariants Φ per composite "
        "GFSM state.",
    )
    p.add_argument("--data-root", type=Path, default=Path("data"))
    p.add_argument("--gfsm-dir", type=Path, required=True,
                   help="dir containing <topology>.gfsm.json + manifest")
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


def _resolve_fb_to_col(
    topo: str, gfsm_dir: Path
) -> dict[tuple[str, str], str]:
    gfsm_path = gfsm_dir / f"{topo}.gfsm.json"
    if not gfsm_path.exists():
        raise InvariantsError(f"gfsm json not found: {gfsm_path}")
    components = load_gfsm_components(json.loads(gfsm_path.read_text()))
    profile = get_profile(topo)
    state_vars = [str(v) for v in profile.state_vars]
    if len(state_vars) != len(components):
        raise InvariantsError(
            f"{topo}: profile state_vars ({len(state_vars)}) does not "
            f"match gfsm components ({len(components)})"
        )
    # ORDERING CONTRACT (load-bearing): components are gfsm-ordered by
    # (plc, fb.name) ascending (see gfsm.compose._ordered_components);
    # profile.state_vars MUST be declared in that same ascending order so
    # this positional zip pairs the right column to each component. The
    # count mismatch above catches length drift; a same-length REORDER is
    # NOT caught here — it is verified end-to-end by the ctown golden test
    # (every label_frame output must be a valid gfsm `states` key).
    return {c: col for c, col in zip(components, state_vars)}


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.all:
        topologies = (
            sorted(
                d.name
                for d in args.gfsm_dir.iterdir()
                if d.is_dir()
                and not d.name.startswith((".", "_"))
                and (d / f"{d.name}.gfsm.json").exists()
            )
            if args.gfsm_dir.exists()
            else []
        )
    else:
        topologies = [args.topology]

    overall_ok = True
    had_error = False
    for topo in topologies:
        out = args.out if args.out else (
            args.data_root / "generated" / topo / "invariants")
        try:
            fb_to_col = _resolve_fb_to_col(topo, args.gfsm_dir)
            manifest = mine_topology(
                topology=topo, data_root=args.data_root,
                gfsm_dir=args.gfsm_dir, out_dir=out,
                fb_to_col=fb_to_col,
                min_observations=args.min_observations,
                max_evals=args.max_evals, seed=args.seed,
                keep_going=not args.strict,
            )
        except (InvariantsError, StlError) as exc:
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
