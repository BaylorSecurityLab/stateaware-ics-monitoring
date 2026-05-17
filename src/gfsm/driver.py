"""Stage-4 driver: orchestrate GFSM build across one topology.

Mirrors src/st_analyze/driver.py. Sequential by default; Phase I adds the
ProcessPoolExecutor fan-out behind `jobs`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .analysis import FsmStatistics
from .compose import compose_global, global_as_function_block
from .manifest import build_manifest
from .model import (
    FunctionBlock,
    GfsmError,
    LocalFSM,
    Metadata,
    State,
    Transition,
)
from .output import fsm_to_dot, fsm_to_json
from .worker import extract_plc


def _fsm_from_dict(d: dict[str, Any]) -> LocalFSM:
    fbs: list[FunctionBlock] = []
    for fbd in d["function_blocks"]:
        fb = FunctionBlock.new(fbd["name"], fbd["case_variable"])
        for sid, sd in fbd["states"].items():
            st = State(
                id=sd["id"], name=sd["name"],
                transitions_out=list(sd["transitions_out"]),
                transitions_in=list(sd["transitions_in"]),
            )
            fb.states[sid] = st
        for td in fbd["transitions"]:
            fb.transitions.append(Transition(
                id=td["id"], from_state=td["from_state"],
                to_state=td["to_state"], condition=td["condition"],
                raw_expression=td["raw_expression"],
            ))
        fbs.append(fb)
    md = d["metadata"]
    return LocalFSM(
        function_blocks=fbs,
        metadata=Metadata(
            md["source_file"],
            # extraction_date is wall-clock; normalise to "" so written
            # artefacts are byte-for-byte identical across repeated runs.
            "",
            md["total_states"], md["total_transitions"],
        ),
    )


def _run_workers(
    units: list[tuple[str, str]], jobs: int
) -> list[dict[str, Any]]:
    # Sequential implementation; Phase I overrides for jobs > 1.
    return [extract_plc(name, path) for name, path in units]


def _gfsm_to_dict(g) -> dict[str, Any]:
    return {
        "initial": g.initial,
        "states": {sid: list(tup) for sid, tup in g.states.items()},
        "transitions": g.transitions,
        "metadata": {
            "source_file": g.metadata.source_file,
            # extraction_date is wall-clock; omit from written JSON to keep
            # output byte-for-byte deterministic across repeated runs.
            "extraction_date": "",
            "total_states": g.metadata.total_states,
            "total_transitions": g.metadata.total_transitions,
        },
        "max_states": g.max_states,
    }


def analyze_topology(
    *,
    generated_dir: Path,
    topology: str,
    out_dir: Path | None,
    max_states: int = 100_000,
    jobs: int = 1,
) -> dict[str, Any]:
    topo_dir = Path(generated_dir) / topology
    analysis_dir = topo_dir / "analysis"
    src_manifest_path = analysis_dir / f"{topology}_analysis_manifest.json"
    if not src_manifest_path.exists():
        raise GfsmError(
            f"Stage 2 analysis manifest not found: {src_manifest_path}"
        )
    src_text = src_manifest_path.read_text()
    try:
        src_manifest = json.loads(src_text)
    except json.JSONDecodeError as exc:
        raise GfsmError(
            f"invalid Stage 2 manifest {src_manifest_path}: {exc}"
        ) from exc

    out = Path(out_dir) if out_dir is not None else topo_dir / "gfsm"
    out.mkdir(parents=True, exist_ok=True)

    plcs = sorted(
        src_manifest.get("plcs", []), key=lambda p: p["name"]
    )
    units: list[tuple[str, str]] = []
    for plc in plcs:
        ast_name = plc.get("artifacts", {}).get("ast_xml")
        if ast_name:
            units.append((plc["name"], str(analysis_dir / ast_name)))

    results = _run_workers(units, jobs)
    results.sort(key=lambda r: r["name"])

    fsms: dict[str, LocalFSM] = {}
    plc_entries: list[dict[str, Any]] = []
    stage2_by_name = {p["name"]: p for p in plcs}

    for res in results:
        name = res["name"]
        stage2 = stage2_by_name.get(name, {})
        stage2_fsms = stage2.get("st_gen_fsms", [])
        status = res["status"]
        errors = list(res["errors"])
        artifacts: dict[str, str] = {}

        if res["fsm"] is not None:
            lf = _fsm_from_dict(res["fsm"])
            fsms[name] = lf
            fsm_json_f = f"{Path(res['ast_path']).stem.replace('.ast', '')}.fsm.json"
            fsm_dot_f = fsm_json_f[:-5] + ".dot"
            (out / fsm_json_f).write_text(fsm_to_json(lf))
            (out / fsm_dot_f).write_text(fsm_to_dot(lf))
            artifacts = {"fsm_json": fsm_json_f, "fsm_dot": fsm_dot_f}
            if stage2_fsms and res["counts"]["function_blocks"] == 0:
                status = "error"
                errors.append(
                    "Stage 2 lists FSMs but extraction found no blocks"
                )
        elif not stage2_fsms:
            # Legitimately no FSM (e.g. anytown/ctown PLC2/PLC3): Stage 2
            # listed no st_gen_fsms and extraction found no function blocks.
            # The real Stage 2 manifest marks these "ok" (not an error), so
            # Stage 4 must not fail the topology over them. Record "skipped":
            # excluded from composition, counts as ok for all_ok / exit code.
            status = "skipped"
            errors = []
        else:
            # Stage 2 expected FSMs but extraction produced none → real error.
            status = "error"

        plc_entries.append({
            "name": name,
            "ast_file": Path(res["ast_path"]).name,
            "status": status,
            "errors": errors,
            "artifacts": artifacts,
            "counts": res["counts"],
            "stage2_fsms": stage2_fsms,
        })

    all_ok = all(e["status"] in ("ok", "skipped") for e in plc_entries)

    if fsms:
        g = compose_global(
            fsms, max_states=max_states,
            source_file=f"{topology} (composed)",
        )
        (out / f"{topology}.gfsm.json").write_text(
            json.dumps(_gfsm_to_dict(g), indent=2, ensure_ascii=False) + "\n"
        )
        (out / f"{topology}.gfsm.dot").write_text(_gfsm_dot(g))
        gfb = global_as_function_block(g)
        st = FsmStatistics.analyze(gfb)
        (out / f"{topology}.gfsm.analysis.json").write_text(
            json.dumps({
                "total_states": st.total_states,
                "total_transitions": st.total_transitions,
                "avg_transitions_per_state": st.avg_transitions_per_state,
                "max_transitions_from_state": st.max_transitions_from_state,
                "unreachable_states": st.unreachable_states,
                "dead_states": st.dead_states,
                "cycles": st.cycles,
            }, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        )
        gfsm_summary = {
            "states": g.metadata.total_states,
            "transitions": g.metadata.total_transitions,
            "initial": g.initial,
        }
    else:
        gfsm_summary = {"states": 0, "transitions": 0, "initial": ""}

    manifest = build_manifest(
        topology=topology,
        source_manifest_name=src_manifest_path.name,
        source_manifest_text=src_text,
        plc_entries=plc_entries,
        gfsm_summary=gfsm_summary,
    )
    manifest["all_ok"] = all_ok
    (out / f"{topology}_gfsm_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    return manifest


def _gfsm_dot(g) -> str:
    parts = [f'digraph "{g.metadata.source_file}" {{\n']
    parts.append("    rankdir=LR;\n")
    parts.append(
        "    node [shape=circle, style=filled, fillcolor=lightblue];\n"
    )
    parts.append("    edge [fontsize=10];\n\n")
    for sid in g.states.keys():
        parts.append(f'    "{sid}" [label="{sid}"];\n')
    parts.append("\n")
    for t in g.transitions:
        label = t["guard"].replace('"', '\\"').replace("\n", "\\n")
        parts.append(
            f'    "{t["from"]}" -> "{t["to"]}" [label="{label}"];\n'
        )
    parts.append("}")
    return "".join(parts)
