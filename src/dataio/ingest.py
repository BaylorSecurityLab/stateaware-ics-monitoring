"""dataio-ingest: normalize raw Downloads datasets into committed data/<topo>/dataset/."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .manifest import build_dataset_manifest
from .model import DataIoError
from .readers import anytown as r_anytown
from .readers import ctown as r_ctown

TOPOLOGIES = ("anytown", "ctown")


def _write_csv(df, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return str(path.name)


def ingest_topology(topology: str, *, raw_root: Path, data_root: Path) -> Path:
    ds = Path(data_root) / topology / "dataset"
    (ds / "calibration").mkdir(parents=True, exist_ok=True)
    (ds / "evaluation").mkdir(parents=True, exist_ok=True)

    if topology == "ctown":
        cal, ev, colmap, src = r_ctown.build_normalized(raw_root)
        cal_frames, eval_named, note = [cal], [("test", ev)], r_ctown.SOURCE_NOTE
        windows = r_ctown.TEST_ATTACKS
    elif topology == "anytown":
        cal_frames, eval_named, colmap, src = r_anytown.build_normalized(raw_root)
        note, windows = "anytown DHALSIM disruptive-anomalies dataset", []
    else:
        raise DataIoError(f"unknown topology: {topology}")

    cal_rel = []
    for i, df in enumerate(cal_frames):
        name = "calibration.csv" if len(cal_frames) == 1 else f"cal_{i:04d}.csv"
        _write_csv(df, ds / "calibration" / name)
        cal_rel.append(f"calibration/{name}")
    ev_rel = []
    for name, df in eval_named:
        if "label" not in df.columns:
            raise DataIoError(f"{topology}: eval frame '{name}' missing label")
        _write_csv(df, ds / "evaluation" / f"{name}.csv")
        ev_rel.append(f"evaluation/{name}.csv")

    man = build_dataset_manifest(
        topology=topology, source_name=src, source_note=note, fmt="csv",
        root=ds, calibration_files=cal_rel, evaluation_files=ev_rel,
        column_map=colmap, attack_windows=windows,
    )
    (ds / "dataset_manifest.yaml").write_text(yaml.safe_dump(man, sort_keys=True))
    return ds


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dataio-ingest",
        description="Normalize raw attack datasets into data/<topo>/dataset/.")
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--topology", choices=TOPOLOGIES)
    grp.add_argument("--all", action="store_true")
    p.add_argument("--raw-root", type=Path, default=Path.home() / "Downloads")
    p.add_argument("--data-root", type=Path, default=Path("data"))
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    topos = list(TOPOLOGIES) if args.all else [args.topology]
    rc = 0
    for t in topos:
        try:
            out = ingest_topology(t, raw_root=args.raw_root,
                                  data_root=args.data_root)
            print(f"{t}: wrote {out}", file=sys.stderr)
        except (DataIoError, FileNotFoundError) as exc:
            print(f"error: {t}: {exc}", file=sys.stderr)
            rc = 2
    return rc


if __name__ == "__main__":
    sys.exit(main())
