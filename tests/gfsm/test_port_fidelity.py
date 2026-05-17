import json
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest

from gfsm.extractor import FsmExtractor
from gfsm.output import fsm_to_dot, fsm_to_json

REPO = Path(__file__).resolve().parents[2]
GEN = REPO / "data" / "generated"
RUST_SRC = Path(os.environ.get("TEMP", "/tmp")) / "fsm-extractor"
TOPOS = ["anytown", "ctown", "ltown"]


def _norm_json(text: str) -> str:
    obj = json.loads(text)
    if isinstance(obj, dict) and "metadata" in obj:
        obj["metadata"]["extraction_date"] = "NORMALIZED"
    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True)


@lru_cache(maxsize=1)
def _rust_binary() -> str | None:
    if shutil.which("cargo") is None:
        return None
    if not (RUST_SRC / "Cargo.toml").exists():
        return None
    try:
        subprocess.run(
            ["cargo", "build", "--release"],
            cwd=RUST_SRC, check=True, capture_output=True, timeout=600,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    exe = "plc-fsm-analyzer" + (".exe" if os.name == "nt" else "")
    path = RUST_SRC / "target" / "release" / exe
    return str(path) if path.exists() else None


def _ast_inputs() -> list[Path]:
    out: list[Path] = []
    for topo in TOPOS:
        ad = GEN / topo / "analysis"
        if ad.is_dir():
            out.extend(sorted(ad.glob("*.ast.xml")))
    return out


_INPUTS = _ast_inputs()


@pytest.mark.skipif(not _INPUTS, reason="generated AST inputs missing")
@pytest.mark.parametrize("ast", _INPUTS, ids=lambda p: p.stem)
def test_python_json_matches_rust(ast: Path):
    binary = _rust_binary()
    if binary is None:
        pytest.skip("cargo / Rust reference binary unavailable")
    rust = subprocess.run(
        [binary, "extract", str(ast), "--format", "json"],
        check=True, capture_output=True, text=True,
    ).stdout
    py = fsm_to_json(FsmExtractor.from_path(ast).extract())
    assert _norm_json(py) == _norm_json(rust), ast.name


@pytest.mark.skipif(not _INPUTS, reason="generated AST inputs missing")
@pytest.mark.parametrize("ast", _INPUTS, ids=lambda p: p.stem)
def test_python_dot_matches_rust(ast: Path):
    binary = _rust_binary()
    if binary is None:
        pytest.skip("cargo / Rust reference binary unavailable")
    rust = subprocess.run(
        [binary, "extract", str(ast), "--format", "dot"],
        check=True, capture_output=True, text=True,
    ).stdout
    py = fsm_to_dot(FsmExtractor.from_path(ast).extract())
    # Rust println! appends a trailing newline; strip both ends to compare
    # the document body byte-for-byte.
    assert py.strip() == rust.strip(), ast.name
