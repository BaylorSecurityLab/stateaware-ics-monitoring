# Installation

This project is managed with [`uv`](https://docs.astral.sh/uv/). All
dependencies except the STL engine resolve normally; **`rtamt` requires special
handling** — read the STL-engine section before you run anything in Stage 3
(`stl-monitor` / `ics-monitor`) or the Stage-3 test suite.

## 1. Standard setup (Windows, native)

Prerequisites: `uv` (>= 0.9) and `git` on `PATH`. `uv` provisions its own
CPython (this project resolves on Python **3.13**; the repo `requires-python`
is `>=3.13`).

```powershell
uv sync --extra dev          # creates .venv, installs everything incl. rtamt-from-git
uv run --no-sync pytest -q   # baseline / full suite
```

`uv sync` reads `[tool.uv.sources]` in `pyproject.toml`, which pins `rtamt` to a
specific git commit (see below). No `pip` is used (the venv has no `pip`).

## 2. The STL engine: `rtamt` from git (not PyPI)

### Why not PyPI

The only `rtamt` release on PyPI is **0.3.5**, and its metadata **hard-pins
`antlr4-python3-runtime==4.7`**. antlr4 4.7's `Lexer.py` does
`from typing.io import TextIO`; the stdlib `typing.io` pseudo-module was
**removed in Python 3.12**, so `rtamt==0.3.5` cannot import on this project's
Python (>=3.13). Overriding to a modern antlr4 (4.13) does **not** work either:
rtamt 0.3.5's ANTLR parser is serialized at ATN **version 3** (antlr 4.7) and a
modern runtime rejects it (`Could not deserialize ATN with version 3`).

### What works

`pip`/`uv` building **`rtamt` from the git HEAD** produces **`rtamt==0.4.10`**,
whose ANTLR parser is regenerated for **`antlr4-python3-runtime==4.7.2`** (pulled
in automatically). 4.7.2 still has the `from typing.io import TextIO` line, but
that is the *only* incompatibility, and it is fixed by a 5-line compatibility
shim that registers a synthetic `typing.io` exposing `typing.IO/TextIO/BinaryIO`
before `rtamt` is imported.

Pinned in `pyproject.toml`:

```toml
[tool.uv.sources]
rtamt = { git = "https://github.com/nickovic/rtamt", rev = "5cb70d15615790536fae85a05e7ee76a38b4e079" }
```

The compat shim lives in two places (both committed):

- `conftest.py` (repo root) — applied at pytest session start, before any test
  imports `rtamt`.
- `src/stl/_rtamt_compat.py` — imported at the top of `src/stl/evaluate.py`
  (and re-applied inside the `ProcessPoolExecutor` workers, which re-import the
  module under Windows `spawn`) so the shim is active in production runs too.

Verify the engine works:

```powershell
uv run --no-sync python -c "import conftest; import rtamt; s=rtamt.StlDiscreteTimeSpecification(); s.declare_var('x','float'); s.spec='x >= 0.0'; s.parse(); print([r[1] for r in s.evaluate({'time':[0,1],'x':[1.0,-1.0]})])"
# expected: [1.0, -1.0]
```

(The Stage-3 test gate `tests/stl/test_rtamt_available.py` checks the same.)

## 3. WSL fallback (only if the native git build fails)

The native Windows build of `rtamt` from git **succeeded** during setup, so WSL
is **not required**. Keep this path documented in case a future machine cannot
build it natively (e.g. no C/C++ toolchain for the antlr4 sdist).

WSL Ubuntu is available on this machine (`wsl -l -v` → `Ubuntu`, WSL2). In WSL
with a Python **<= 3.11**, `rtamt` 0.4.10 + antlr4 4.7.2 work *without the shim*
because `typing.io` still exists there.

```bash
# inside WSL Ubuntu
sudo apt-get update && sudo apt-get install -y python3.11 python3.11-venv build-essential git
cd /mnt/c/Users/bkoro/projects/stateaware-ics-monitoring
uv venv --python 3.11 .venv-wsl
uv pip install --python .venv-wsl "git+https://github.com/nickovic/rtamt@5cb70d15615790536fae85a05e7ee76a38b4e079"
uv pip install --python .venv-wsl -e ".[dev]"
.venv-wsl/bin/python -m pytest -q
```

Notes / caveats for the WSL path:
- The `data/` git submodule and `~/Downloads` raw datasets are reached via
  `/mnt/c/...` from WSL; pass `--raw-root "/mnt/c/Users/bkoro/Downloads"` and
  `--data-root /mnt/c/Users/bkoro/projects/stateaware-ics-monitoring/data` to
  `dataio-ingest`.
- On Python <= 3.11 the `typing.io` shim is a harmless no-op (`conftest.py`
  guards with `if "typing.io" not in sys.modules`).
- Cross-OS line endings: keep `.venv-wsl` separate from the Windows `.venv`.

## 4. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'typing.io'` | shim not applied before `rtamt` import | run under pytest (root `conftest.py`) or import `stl._rtamt_compat` first |
| `Could not deserialize ATN with version 3 (expected 4)` | `rtamt==0.3.5` (PyPI) + modern antlr4 | use the git-pinned `rtamt` (Section 2), never PyPI |
| `uv sync` resolution error mentioning `rtamt>=0.4` / `antlr4-python3-runtime==4.7` | stale pin / PyPI rtamt | ensure `[tool.uv.sources]` git pin is present; `uv lock --upgrade-package rtamt` |
| native build of antlr4 sdist fails (no compiler) | missing C toolchain | use the WSL fallback (Section 3) |
