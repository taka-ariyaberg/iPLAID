# Echo dispenser in iPLAID — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Echo acoustic liquid handler as a selectable dispenser in iPLAID alongside iDOT, with a UI dropdown, optional source-plate-layout import, and zero behavioral change to the iDOT path.

**Architecture:** Strategy subpackage `src/iplaid/dispensers/` with a `Dispenser` Protocol implemented by `IDotDispenser` and `EchoDispenser`. Pipeline dispatches via `cfg["dispenser"]` (default `"idot"`). The shared dispense table (`all_rows` + `liquid_table`) feeds either backend. Source-plate-import generalizes `build_liquid_table` to optionally consume a user-supplied layout, benefiting both backends.

**Tech Stack:** Python 3.11, pandas, pydantic v2, FastAPI, React, TypeScript, Vite. Tests: pytest. Frontend e2e: manual (no test framework configured today).

**Source spec:** [`docs/superpowers/specs/2026-05-02-echo-dispenser-design.md`](../specs/2026-05-02-echo-dispenser-design.md)

**Working directory:** All paths are relative to the iPLAID repo root (`/Users/takar834/Documents/UU/TIMED/Tools/iPLAID/`). The first action when executing this plan is `cd` to that directory.

---

## File structure (final state)

```
src/iplaid/
  __init__.py                                       MODIFY  (export get_dispenser, list_dispensers)
  pipeline.py                                       MODIFY  (uses dispenser registry; add increment step)
  output.py                                         MODIFY  (shrink: keep shared builders; re-export iDOT funcs from dispensers/idot.py)
  validators.py                                     MODIFY  (re-export validate_export_file from dispensers/idot.py)
  normalization.py                                  MODIFY  (add apply_dispenser_increment)
  io.py                                             MODIFY  (validate_config_dict accepts dispenser field; add load_plate_specs_for_dispenser)
  source_plate_prep.py                              MODIFY  (read dispense limits from passed plate specs instead of hardcoded)
  dispensers/
    __init__.py                                     CREATE  (registry: get_dispenser, list_dispensers)
    base.py                                         CREATE  (Dispenser Protocol, DispenserSpec dataclass, exceptions)
    idot.py                                         CREATE  (IDotDispenser; iDOT functions moved from output.py + validators.py)
    echo.py                                         CREATE  (EchoDispenser; Echo writer + validator + helpers)
data/
  echo_plate_specs.json                             CREATE  (Echo plate catalog: 384PP_DMSO2)
backend/app/
  models.py                                         MODIFY  (RunConfigModel.dispenser field; source_layout_file field)
  main.py                                           MODIFY  (/bootstrap returns dispensers + plate_types_by_dispenser)
  designer.py                                       MODIFY  (forward source_layout_path to run_pipeline_with_inputs)
frontend/src/
  types.ts                                          MODIFY  (RunConfig.dispenser; BootstrapResponse new fields)
  workbenchState.tsx                                MODIFY  (dispenser default; reset sourceplate_type and source_layout_file on dispenser change)
  components/workbench/RunConfigPanel.tsx           MODIFY  (Dispenser dropdown above Source plate; dependent plate options; optional source-layout file picker)
  pages/ResultsPage.tsx                             MODIFY  (plate spec lookup uses plate_types_by_dispenser)
tests/
  test_pipeline.py                                  CREATE  (was empty: golden test for iDOT, then for Echo, then for source-import)
  test_dispensers.py                                CREATE  (registry + interface conformance)
  test_dispensers_idot.py                           CREATE  (iDOT-specific writer/validator unit tests)
  test_dispensers_echo.py                           CREATE  (Echo writer/validator unit tests + helpers)
  test_normalization_increment.py                   CREATE  (apply_dispenser_increment unit tests)
  test_source_plate_import.py                       CREATE  (build_liquid_table existing_layout=)
  golden/
    idot_basic/                                     CREATE  (input layout/meta/config + expected protocol/liquids/imeta)
    echo_basic/                                     CREATE  (input + expected Echo CSV)
    echo_with_layout/                               CREATE  (input + supplied layout + expected Echo CSV using imported wells)
data/test_fixtures/                                 CREATE  (deterministic test inputs that don't depend on inputs/ examples)
```

---

## Phase M — Establish regression fence and migrate iDOT into the registry

> **Why first:** iPLAID has no byte-equal regression tests today (`tests/test_pipeline.py` is empty, no `tests/golden/`). Refactoring iDOT before the fence is in place is unsafe. M1–M2 add the fence; M3–M6 do the refactor under its protection.

### Task M1: Create iDOT golden fixture (input + expected outputs)

**Files:**
- Create: `tests/golden/idot_basic/layout.csv`
- Create: `tests/golden/idot_basic/meta.csv`
- Create: `tests/golden/idot_basic/config.json`

- [ ] **Step 1: Pick a deterministic minimal input.** Copy iPLAID's existing `inputs/layouts/compound_layout_example.csv` and `inputs/meta/meta_example.csv` into the golden directory. Inspect them:

```bash
cd /Users/takar834/Documents/UU/TIMED/Tools/iPLAID
mkdir -p tests/golden/idot_basic
cp inputs/layouts/compound_layout_example.csv tests/golden/idot_basic/layout.csv
cp inputs/meta/meta_example.csv tests/golden/idot_basic/meta.csv
head -3 tests/golden/idot_basic/layout.csv tests/golden/idot_basic/meta.csv
```

Expected: both files print 3 lines without error.

- [ ] **Step 2: Write `tests/golden/idot_basic/config.json`** with deterministic inputs. Keep `output_timestamp_format` fixed to a constant string so timestamps don't drift between runs.

```json
{
  "user_name": "GoldenTest",
  "protocol_name": "IDOT_BASIC_GOLDEN",
  "layout_file": "layout.csv",
  "meta_file": "meta.csv",
  "sourceplate_type": "S.100 Plate",
  "target_plate_type": "MWP 384",
  "working_volume_ul": 40,
  "max_dmso_pct": 0.1,
  "source_prep_overage_pct": 0.30,
  "min_pipette_volume_uL": 1.0,
  "dilution_solvent": "DMSO",
  "source_well_fill_pct": 0.70,
  "standard_prep_volume_uL": 1000.0,
  "output_timestamp_format": "FROZEN-TIMESTAMP"
}
```

- [ ] **Step 3: Commit the fixture inputs (no expected outputs yet).**

```bash
git add tests/golden/idot_basic/layout.csv tests/golden/idot_basic/meta.csv tests/golden/idot_basic/config.json
git commit -m "test(golden): add iDOT basic fixture inputs"
```

---

### Task M2: Generate iDOT golden expected outputs and lock them with a regression test

**Files:**
- Create: `tests/test_pipeline.py` (was empty)
- Create: `tests/golden/idot_basic/expected_protocol.csv`
- Create: `tests/golden/idot_basic/expected_liquids.csv`
- Create: `tests/golden/idot_basic/expected_imeta.csv`

- [ ] **Step 1: Write the failing test in `tests/test_pipeline.py`.**

```python
"""End-to-end regression tests for run_pipeline_with_inputs.

Locks the iDOT and (later) Echo outputs byte-for-byte against captured goldens.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from iplaid.pipeline import run_pipeline_with_inputs  # noqa: E402


GOLDEN_DIR = Path(__file__).parent / "golden"


def _read_bytes(p: Path) -> bytes:
    return Path(p).read_bytes()


def _run_golden(fixture_name: str, tmp_path: Path) -> dict:
    """Copy a golden fixture into tmp_path and run the pipeline against it."""
    src = GOLDEN_DIR / fixture_name
    work = tmp_path / fixture_name
    work.mkdir(parents=True)
    shutil.copy(src / "layout.csv", work / "layout.csv")
    shutil.copy(src / "meta.csv", work / "meta.csv")
    cfg = json.loads((src / "config.json").read_text())
    out_dir = work / "out"
    out_dir.mkdir()
    return run_pipeline_with_inputs(
        config=cfg,
        layout_path=work / "layout.csv",
        meta_path=work / "meta.csv",
        output_dir=out_dir,
        include_source_prep=False,
    )


def test_idot_basic_protocol_byte_equal(tmp_path: Path) -> None:
    result = _run_golden("idot_basic", tmp_path)
    expected = _read_bytes(GOLDEN_DIR / "idot_basic" / "expected_protocol.csv")
    actual = _read_bytes(result["paths"]["out_idot"])
    assert actual == expected, "iDOT protocol CSV diverged from golden"


def test_idot_basic_liquids_byte_equal(tmp_path: Path) -> None:
    result = _run_golden("idot_basic", tmp_path)
    expected = _read_bytes(GOLDEN_DIR / "idot_basic" / "expected_liquids.csv")
    actual = _read_bytes(result["paths"]["out_liquids"])
    assert actual == expected


def test_idot_basic_imeta_byte_equal(tmp_path: Path) -> None:
    result = _run_golden("idot_basic", tmp_path)
    expected = _read_bytes(GOLDEN_DIR / "idot_basic" / "expected_imeta.csv")
    actual = _read_bytes(result["paths"]["out_imeta"])
    assert actual == expected
```

- [ ] **Step 2: Run the tests; they MUST fail (no expected files yet).**

```bash
cd /Users/takar834/Documents/UU/TIMED/Tools/iPLAID
python -m pytest tests/test_pipeline.py -v
```

Expected: 3 tests fail with `FileNotFoundError` for the `expected_*.csv` files.

- [ ] **Step 3: Capture the goldens by running the pipeline once and copying its outputs.**

Use a one-shot helper script in a Python REPL or a temporary file:

```bash
python -c "
import json, shutil, sys
from pathlib import Path
sys.path.insert(0, 'src')
from iplaid.pipeline import run_pipeline_with_inputs

src = Path('tests/golden/idot_basic')
work = Path('/tmp/idot_capture'); work.mkdir(exist_ok=True)
shutil.copy(src/'layout.csv', work/'layout.csv')
shutil.copy(src/'meta.csv', work/'meta.csv')
cfg = json.loads((src/'config.json').read_text())
out = work/'out'; out.mkdir(exist_ok=True)
r = run_pipeline_with_inputs(config=cfg, layout_path=work/'layout.csv', meta_path=work/'meta.csv', output_dir=out, include_source_prep=False)
shutil.copy(r['paths']['out_idot'],     src/'expected_protocol.csv')
shutil.copy(r['paths']['out_liquids'],  src/'expected_liquids.csv')
shutil.copy(r['paths']['out_imeta'],    src/'expected_imeta.csv')
print('captured to', src)
"
```

- [ ] **Step 4: Re-run the tests; they MUST pass.**

```bash
python -m pytest tests/test_pipeline.py -v
```

Expected: 3 tests pass. If any fails, the pipeline is non-deterministic — investigate before proceeding (likely a timestamp leaking through).

- [ ] **Step 5: Commit the regression fence.**

```bash
git add tests/test_pipeline.py tests/golden/idot_basic/expected_*.csv
git commit -m "test(pipeline): lock iDOT byte-equal regression fence"
git tag pre-dispenser-migration
```

---

### Task M3: Create the dispenser interface (base.py + empty registry)

**Files:**
- Create: `src/iplaid/dispensers/__init__.py`
- Create: `src/iplaid/dispensers/base.py`
- Create: `tests/test_dispensers.py`

- [ ] **Step 1: Write the failing test in `tests/test_dispensers.py`.**

```python
"""Dispenser registry and interface conformance tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from iplaid.dispensers import get_dispenser, list_dispensers
from iplaid.dispensers.base import Dispenser, DispenserSpec, UnknownDispenserError


def test_dispenser_spec_is_frozen_dataclass() -> None:
    spec = DispenserSpec(
        name="test",
        display_name="Test",
        plate_specs_path="test_specs.json",
        min_increment_nL=0.0,
        default_sourceplate_type="X",
        default_target_plate_type="Y",
    )
    with pytest.raises(Exception):  # FrozenInstanceError
        spec.name = "other"  # type: ignore[misc]


def test_get_dispenser_unknown_raises() -> None:
    with pytest.raises(UnknownDispenserError):
        get_dispenser("nope")


def test_list_dispensers_returns_specs() -> None:
    specs = list_dispensers()
    assert len(specs) >= 1
    assert all(isinstance(s, DispenserSpec) for s in specs)
```

- [ ] **Step 2: Run; verify failure.**

```bash
python -m pytest tests/test_dispensers.py -v
```

Expected: ImportError on `iplaid.dispensers`.

- [ ] **Step 3: Create `src/iplaid/dispensers/base.py`.**

```python
"""Dispenser strategy interface.

Each dispenser implements this Protocol. The pipeline uses get_dispenser(cfg["dispenser"])
to dispatch dispenser-specific build/write/validate work.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

import pandas as pd


class UnknownDispenserError(ValueError):
    """Raised when cfg['dispenser'] does not match a registered dispenser."""


class SourceLayoutError(ValueError):
    """Raised when a user-supplied source-plate layout is invalid or incomplete."""


@dataclass(frozen=True)
class DispenserSpec:
    """Static metadata for a dispenser. Loaded from the registry."""
    name: str
    display_name: str
    plate_specs_path: str  # relative to <project_root>/data/
    min_increment_nL: float  # 0 means no rounding (iDOT); 2.5 for Echo
    default_sourceplate_type: str
    default_target_plate_type: str


@runtime_checkable
class Dispenser(Protocol):
    spec: DispenserSpec

    def load_plate_specs(self, project_root: Path) -> dict: ...

    def build_protocol(
        self,
        all_rows: pd.DataFrame,
        liquid_table: pd.DataFrame,
        *,
        cfg: dict,
        source_specs: dict,
    ) -> pd.DataFrame: ...

    def write_protocol(self, protocol_df: pd.DataFrame, out_path: Path) -> None: ...

    def write_liquids(self, liquid_table_export: pd.DataFrame, out_path: Path) -> None: ...

    def validate_export(
        self,
        out_path: Path,
        *,
        protocol_name: str,
        user_name: str,
    ) -> tuple[pd.DataFrame, int]: ...
```

- [ ] **Step 4: Create `src/iplaid/dispensers/__init__.py`.**

```python
"""Dispenser registry. Add new dispensers by importing them and adding to _REGISTRY."""
from __future__ import annotations

from .base import Dispenser, DispenserSpec, SourceLayoutError, UnknownDispenserError

# Imports populated as dispensers are added (see Task M5, E1.4).
_REGISTRY: dict[str, Dispenser] = {}


def get_dispenser(name: str) -> Dispenser:
    if name not in _REGISTRY:
        raise UnknownDispenserError(
            f"Unknown dispenser '{name}'. Registered: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[name]


def list_dispensers() -> list[DispenserSpec]:
    return [d.spec for d in _REGISTRY.values()]


def _register(dispenser: Dispenser) -> None:
    """Internal: register a dispenser instance under its spec.name."""
    _REGISTRY[dispenser.spec.name] = dispenser


__all__ = [
    "Dispenser",
    "DispenserSpec",
    "SourceLayoutError",
    "UnknownDispenserError",
    "get_dispenser",
    "list_dispensers",
]
```

- [ ] **Step 5: Run tests; the spec/unknown tests pass; `test_list_dispensers_returns_specs` fails (registry empty).**

```bash
python -m pytest tests/test_dispensers.py -v
```

Expected: 2 pass, 1 fail (`assert len(specs) >= 1`). That failure is intentional — fixed in Task M5.

- [ ] **Step 6: Commit.**

```bash
git add src/iplaid/dispensers/__init__.py src/iplaid/dispensers/base.py tests/test_dispensers.py
git commit -m "feat(dispensers): add registry skeleton and Dispenser Protocol"
```

---

### Task M4: Move iDOT functions into `dispensers/idot.py` (no behavior change)

**Files:**
- Create: `src/iplaid/dispensers/idot.py`
- Modify: `src/iplaid/output.py` (re-export iDOT funcs from new location)
- Modify: `src/iplaid/validators.py` (re-export `validate_export_file`)

- [ ] **Step 1: Read current iDOT functions to confirm exact content.** Open `src/iplaid/output.py` and `src/iplaid/validators.py` and note these symbols:
  - `output.py`: `format_protocol_volume_ul`, `wells_96`, `build_full_protocol`, `write_protocol_file`, `write_liquids_file`, `write_outputs`
  - `validators.py`: `validate_export_file`

`wells_96` is shared (used by `build_liquid_table`) and stays in `output.py`. The other six move.

- [ ] **Step 2: Create `src/iplaid/dispensers/idot.py`** by moving the six functions verbatim. Add the `IDotDispenser` class that wraps them as methods.

```python
"""iDOT dispenser implementation.

Functions previously in src/iplaid/output.py and src/iplaid/validators.py live here.
output.py and validators.py re-export them for import-path stability.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from .base import DispenserSpec
from . import _register


# --------------------------- moved from output.py ---------------------------

def format_protocol_volume_ul(volume_ul: float) -> str:
    """Format a dispense volume exactly as written to the iDOT protocol CSV."""
    return f"{float(volume_ul):05.2f}"


def build_full_protocol(
    all_rows: pd.DataFrame,
    *,
    protocol_name: str,
    user_name: str,
    sourceplate_type: str,
    target_plate_type: str,
    source_specs: dict,
    waste_pos: str = "Waste Tube",
    software_version: str = "1.7.2021.1019",
    date: Optional[str] = None,
    time: Optional[str] = None,
    dispense_to_waste: bool = True,
    dispense_to_waste_cycles: int = 2,
    dispense_to_waste_volume_l: float = 5e-8,
    use_deionisation: bool = True,
    optimization_level: str = "ReorderAndParallel",
    waste_error_handling_level: str = "Ask",
    save_liquids: str = "Ask",
) -> pd.DataFrame:
    """Build full iDOT protocol DataFrame with headers and parameters."""
    if date is None or time is None:
        x = datetime.datetime.now()
        if date is None:
            date = x.strftime("%x")
        if time is None:
            time = x.strftime("%X")

    max_volume_l = float(source_specs.get("max_volume_L_for_protocol", 8.0E-5))

    blocks = []
    sourceplates = all_rows["Source Plate"].unique().tolist()
    targetplates = all_rows["Target Plate"].unique().tolist()

    for sp in sourceplates:
        for tp in targetplates:
            dfx = all_rows.loc[(all_rows["Source Plate"] == sp) & (all_rows["Target Plate"] == tp)].copy()
            if dfx.empty:
                continue

            body = dfx[["Source Well", "Target Well", "Volume [uL]", "Liquid Name"]].copy()
            body["Volume [uL]"] = body["Volume [uL]"].map(format_protocol_volume_ul)

            body = body.reindex(columns=[*body.columns.tolist(), "", "", "", ""], fill_value="")
            body = pd.concat([body.columns.to_frame().T, body], ignore_index=True)
            body.columns = range(len(body.columns))

            subheader = pd.DataFrame([
                [sourceplate_type, sp, "", max_volume_l, target_plate_type, tp, "", waste_pos],
                [
                    f"DispenseToWaste={dispense_to_waste}",
                    f"DispenseToWasteCycles={dispense_to_waste_cycles}",
                    f"DispenseToWasteVolume={dispense_to_waste_volume_l}",
                    f"UseDeionisation={use_deionisation}",
                    f"OptimizationLevel={optimization_level}",
                    f"WasteErrorHandlingLevel={waste_error_handling_level}",
                    f"SaveLiquids={save_liquids}",
                    ""
                ],
            ])

            blocks.append(pd.concat([subheader, body], ignore_index=True))

    file_header = pd.DataFrame([[protocol_name, software_version, user_name, date, time, "", "", ""]])
    fullprotocol = pd.concat([file_header, *blocks], ignore_index=True)
    return fullprotocol


def write_protocol_file(full_protocol: pd.DataFrame, output_path: Path) -> None:
    """Write protocol to iDOT CSV file with proper formatting."""
    full_protocol.to_csv(
        output_path,
        header=False,
        index=False,
        encoding="utf-8-sig",
        lineterminator="\r\n",
    )

    output_path = Path(output_path)
    data = output_path.read_bytes()
    if data.endswith(b"\r\n"):
        output_path.write_bytes(data[:-2])


def write_liquids_file(liquid_table_export: pd.DataFrame, output_path: Path) -> None:
    """Write liquid mapping file."""
    liquid_table_export.to_csv(output_path, index=False)


def write_outputs(
    full_protocol: pd.DataFrame,
    liquid_table_export: pd.DataFrame,
    *,
    out_protocol: Path,
    out_liquids: Path,
) -> None:
    """Write both protocol and liquids files."""
    write_protocol_file(full_protocol, Path(out_protocol))
    write_liquids_file(liquid_table_export, Path(out_liquids))


# ------------------------- moved from validators.py -------------------------

def validate_export_file(
    out_path: Path,
    *,
    protocol_name: str,
    user_name: str,
) -> tuple[pd.DataFrame, int]:
    """Read back the iDOT export and verify file_header invariants. Returns (preview_df, header_row_idx)."""
    # NOTE: keep the body of the existing validators.validate_export_file verbatim.
    # This function is the regression-locked reference; do not "improve" it during the move.
    raise NotImplementedError("Move the body verbatim from validators.py during Task M4.")


# --------------------------- IDotDispenser class ----------------------------

class IDotDispenser:
    spec = DispenserSpec(
        name="idot",
        display_name="iDOT",
        plate_specs_path="source_plate_specs.json",
        min_increment_nL=0.0,
        default_sourceplate_type="S.100 Plate",
        default_target_plate_type="MWP 384",
    )

    def load_plate_specs(self, project_root: Path) -> dict:
        import json
        return json.loads((Path(project_root) / "data" / self.spec.plate_specs_path).read_text())

    def build_protocol(self, all_rows, liquid_table, *, cfg, source_specs):
        return build_full_protocol(
            all_rows,
            protocol_name=str(cfg["protocol_name"]),
            user_name=str(cfg["user_name"]),
            sourceplate_type=str(cfg["sourceplate_type"]),
            target_plate_type=str(cfg["target_plate_type"]),
            source_specs=source_specs,
        )

    def write_protocol(self, protocol_df, out_path):
        write_protocol_file(protocol_df, Path(out_path))

    def write_liquids(self, liquid_table_export, out_path):
        write_liquids_file(liquid_table_export, Path(out_path))

    def validate_export(self, out_path, *, protocol_name, user_name):
        return validate_export_file(Path(out_path), protocol_name=protocol_name, user_name=user_name)


_register(IDotDispenser())
```

- [ ] **Step 3: Replace the `raise NotImplementedError` line in the new `validate_export_file` with the verbatim body** from `src/iplaid/validators.py`. Use `Read` to get the current body, then `Edit` to substitute.

After substitution, confirm:

```bash
grep -A2 "def validate_export_file" src/iplaid/dispensers/idot.py | head
```

Expected: function body present, no NotImplementedError.

- [ ] **Step 4: Update `src/iplaid/output.py`.** Delete the six moved function bodies and add re-exports. Keep `build_compound_and_topup_rows`, `wells_96`, `build_liquid_table`, `attach_and_sort_dispense_rows` in place — they're shared.

```python
# At the top of output.py, after the existing imports, add:
from .dispensers.idot import (  # re-exports for import-path stability
    format_protocol_volume_ul,
    build_full_protocol,
    write_protocol_file,
    write_liquids_file,
    write_outputs,
)

__all__ = [
    "build_compound_and_topup_rows",
    "wells_96",
    "build_liquid_table",
    "attach_and_sort_dispense_rows",
    "format_protocol_volume_ul",
    "build_full_protocol",
    "write_protocol_file",
    "write_liquids_file",
    "write_outputs",
]
```

Then delete the original `format_protocol_volume_ul`, `build_full_protocol`, `write_protocol_file`, `write_liquids_file`, `write_outputs` definitions from `output.py`. **Do not delete `wells_96`, `build_compound_and_topup_rows`, `build_liquid_table`, `attach_and_sort_dispense_rows`.**

- [ ] **Step 5: Update `src/iplaid/validators.py`.** Add a re-export of `validate_export_file` from `dispensers.idot`, then delete the original definition.

```python
# At the top of validators.py, after existing imports, add:
from .dispensers.idot import validate_export_file  # re-export for import-path stability
```

Delete the original `validate_export_file` body. Keep `validate_solvent_normalization` in place.

- [ ] **Step 6: Run the full test suite.**

```bash
python -m pytest -v
```

Expected: ALL tests pass, including the three iDOT goldens from Task M2. If any test fails, the move was non-byte-equal — revert with `git checkout -- src/` and try again.

- [ ] **Step 7: Commit.**

```bash
git add src/iplaid/dispensers/idot.py src/iplaid/output.py src/iplaid/validators.py
git commit -m "refactor(iplaid): move iDOT dispenser into dispensers/idot.py with re-exports"
```

---

### Task M5: Wire `pipeline.py` to use the dispenser registry

**Files:**
- Modify: `src/iplaid/pipeline.py`
- Modify: `src/iplaid/io.py`
- Modify: `tests/test_dispensers.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Add a registry-population test that now passes.** In `tests/test_dispensers.py`, the `test_list_dispensers_returns_specs` test should already pass once `idot.py` is imported. Verify:

```bash
python -m pytest tests/test_dispensers.py -v
```

Expected: 3 pass.

- [ ] **Step 2: Add `test_idot_explicit_dispenser_field`** to `tests/test_pipeline.py`:

```python
def test_idot_explicit_dispenser_field_byte_equal(tmp_path: Path) -> None:
    """cfg with dispenser='idot' produces identical output to cfg with no dispenser field."""
    src = GOLDEN_DIR / "idot_basic"
    work = tmp_path / "explicit"
    work.mkdir()
    shutil.copy(src / "layout.csv", work / "layout.csv")
    shutil.copy(src / "meta.csv", work / "meta.csv")
    cfg = json.loads((src / "config.json").read_text())
    cfg["dispenser"] = "idot"
    out_dir = work / "out"
    out_dir.mkdir()
    result = run_pipeline_with_inputs(
        config=cfg,
        layout_path=work / "layout.csv",
        meta_path=work / "meta.csv",
        output_dir=out_dir,
        include_source_prep=False,
    )
    expected = (GOLDEN_DIR / "idot_basic" / "expected_protocol.csv").read_bytes()
    assert Path(result["paths"]["out_idot"]).read_bytes() == expected
```

- [ ] **Step 3: Run; expect failure.**

```bash
python -m pytest tests/test_pipeline.py::test_idot_explicit_dispenser_field_byte_equal -v
```

Expected: failure (`validate_config_dict` likely rejects the unknown `dispenser` key, or the pipeline ignores it but is unchanged behavior — either way, we want to ensure it routes through the registry).

- [ ] **Step 4: Update `src/iplaid/io.py::validate_config_dict`** to accept the `dispenser` field with default `"idot"` and validate against the registry.

Open `src/iplaid/io.py`, locate `validate_config_dict`. Add at the start of its body:

```python
from .dispensers import get_dispenser, UnknownDispenserError  # local import avoids circular

dispenser_name = config.get("dispenser", "idot")
try:
    get_dispenser(dispenser_name)
except UnknownDispenserError:
    raise ValueError(f"Invalid dispenser '{dispenser_name}'. Use 'idot' or 'echo'.")
config["dispenser"] = dispenser_name  # canonicalize default
```

- [ ] **Step 5: Update `src/iplaid/pipeline.py::_run_pipeline_with_resolved_inputs`.** Locate the section that currently does:

```python
specs = load_source_plate_specs(paths["plate_specs_path"])
source_specs = get_source_plate_spec(specs, cfg["sourceplate_type"])
```

Replace with:

```python
from .dispensers import get_dispenser

disp = get_dispenser(cfg.get("dispenser", "idot"))
specs = disp.load_plate_specs(paths["project_root"])
source_specs = get_source_plate_spec(specs, cfg["sourceplate_type"])
```

Locate the section that currently does:

```python
fullprotocol = build_full_protocol(
    all_rows,
    protocol_name=str(cfg["protocol_name"]),
    user_name=str(cfg["user_name"]),
    sourceplate_type=str(cfg["sourceplate_type"]),
    target_plate_type=str(cfg["target_plate_type"]),
    source_specs=source_specs,
)

# Write output files
write_outputs(
    fullprotocol,
    liquid_table_export,
    out_protocol=paths["out_idot"],
    out_liquids=paths["out_liquids"],
)
```

Replace with:

```python
fullprotocol = disp.build_protocol(
    all_rows,
    liquid_table,
    cfg=cfg,
    source_specs=source_specs,
)

disp.write_protocol(fullprotocol, paths["out_idot"])
disp.write_liquids(liquid_table_export, paths["out_liquids"])
```

Locate the validator call:

```python
preview_df, header_row_idx = validate_export_file(
    paths["out_idot"],
    protocol_name=str(cfg["protocol_name"]),
    user_name=str(cfg["user_name"]),
)
```

Replace with:

```python
preview_df, header_row_idx = disp.validate_export(
    paths["out_idot"],
    protocol_name=str(cfg["protocol_name"]),
    user_name=str(cfg["user_name"]),
)
```

Remove the now-unused imports `from .output import (build_full_protocol, write_outputs)` and `from .validators import validate_export_file` from the top of `pipeline.py`.

- [ ] **Step 6: Run the full suite.**

```bash
python -m pytest -v
```

Expected: ALL tests pass, including the new `test_idot_explicit_dispenser_field_byte_equal`.

- [ ] **Step 7: Commit.**

```bash
git add src/iplaid/pipeline.py src/iplaid/io.py tests/test_pipeline.py
git commit -m "feat(pipeline): dispatch via dispenser registry; default to iDOT"
```

---

### Task M6: Add interface-conformance test

**Files:**
- Modify: `tests/test_dispensers.py`

- [ ] **Step 1: Add a conformance test that loops over registered dispensers and checks the interface.**

Append to `tests/test_dispensers.py`:

```python
from iplaid.dispensers import _REGISTRY


def test_each_registered_dispenser_satisfies_protocol() -> None:
    """Every registered dispenser must implement the Dispenser Protocol."""
    assert len(_REGISTRY) > 0, "Registry must have at least one dispenser"
    for name, disp in _REGISTRY.items():
        assert isinstance(disp, Dispenser), f"{name!r} does not implement Dispenser Protocol"
        assert disp.spec.name == name, f"Spec name {disp.spec.name!r} != registry key {name!r}"
        # All five interface methods must be callable:
        for method in ["load_plate_specs", "build_protocol", "write_protocol",
                       "write_liquids", "validate_export"]:
            assert callable(getattr(disp, method)), f"{name}.{method} not callable"
```

- [ ] **Step 2: Run.**

```bash
python -m pytest tests/test_dispensers.py -v
```

Expected: all pass.

- [ ] **Step 3: Commit.**

```bash
git add tests/test_dispensers.py
git commit -m "test(dispensers): add interface conformance test"
```

**Phase M complete.** iDOT path is now routed through the registry with byte-equal regression tests in place.

---

## Phase E1 — Echo writer

### Task E1.1: Echo plate specs JSON

**Files:**
- Create: `data/echo_plate_specs.json`

- [ ] **Step 1: Create the file.**

```json
{
  "384PP_DMSO2": {
    "wells": 384,
    "rows": 16,
    "cols": 24,
    "dispense_min_nL": 2.5,
    "dispense_max_nL_dmso": 12000,
    "dead_volume_uL_dmso": 15,
    "effective_reservoir_uL": 65,
    "x_offset": 1050,
    "y_offset": -1050,
    "destination_plate_type_default": "Corning_384w_3784",
    "notes": "Echo 384-well low dead volume DMSO source plate. X/Y offsets are vendor defaults; verify against your Echo software profile before first run."
  }
}
```

- [ ] **Step 2: Commit.**

```bash
git add data/echo_plate_specs.json
git commit -m "feat(data): add echo_plate_specs.json with 384PP_DMSO2"
```

---

### Task E1.2: Echo well-padding helpers (TDD)

**Files:**
- Create: `src/iplaid/dispensers/echo.py`
- Create: `tests/test_dispensers_echo.py`

- [ ] **Step 1: Write failing tests.**

```python
"""Echo dispenser unit tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from iplaid.dispensers.echo import (
    _liquid_name_to_sample_name,
    _pad_source_well,
    _unpad_dest_well,
)


def test_pad_source_well_pads_single_digit() -> None:
    assert _pad_source_well("A1") == "A01"
    assert _pad_source_well("B7") == "B07"


def test_pad_source_well_leaves_double_digit() -> None:
    assert _pad_source_well("A12") == "A12"
    assert _pad_source_well("H24") == "H24"


def test_pad_source_well_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        _pad_source_well("BAD")


def test_unpad_dest_well_strips_leading_zero() -> None:
    assert _unpad_dest_well("A01") == "A1"
    assert _unpad_dest_well("B07") == "B7"


def test_unpad_dest_well_leaves_already_unpadded() -> None:
    assert _unpad_dest_well("A1") == "A1"
    assert _unpad_dest_well("H24") == "H24"


def test_liquid_name_to_sample_name() -> None:
    assert _liquid_name_to_sample_name("[gemcitabine][1.0]") == "gemcitabine[1.0]"
    assert _liquid_name_to_sample_name("[dmso][0.0]") == "dmso[0.0]"
```

- [ ] **Step 2: Run; expect ImportError.**

```bash
python -m pytest tests/test_dispensers_echo.py -v
```

- [ ] **Step 3: Create `src/iplaid/dispensers/echo.py` with the helpers (no dispenser class yet).**

```python
"""Echo dispenser implementation.

Vendor format: single-section CSV, 10 fixed columns. Source wells zero-padded ("A07"),
destination wells unpadded ("B2"). Volumes in nL, multiples of 2.5, written as %.1f.
Encoding: utf-8 (no BOM), line terminator: LF.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from .base import DispenserSpec
from . import _register


_WELL_RE = re.compile(r"^([A-Z])(\d+)$")
_LIQUID_RE = re.compile(r"^\[(.*?)\]\[(.*?)\]$")


def _pad_source_well(well: str) -> str:
    """A1 -> A01, B12 -> B12. Always 2-digit number."""
    m = _WELL_RE.match(well)
    if not m:
        raise ValueError(f"Bad well: {well!r}")
    return f"{m.group(1)}{int(m.group(2)):02d}"


def _unpad_dest_well(well: str) -> str:
    """A01 -> A1, B12 -> B12."""
    m = _WELL_RE.match(well)
    if not m:
        raise ValueError(f"Bad well: {well!r}")
    return f"{m.group(1)}{int(m.group(2))}"


def _liquid_name_to_sample_name(liquid_name: str) -> str:
    """[compound][stock_mM] -> compound[stock_mM] (Echo Sample Name format)."""
    m = _LIQUID_RE.match(liquid_name)
    if not m:
        raise ValueError(f"Liquid Name not in [compound][stock] format: {liquid_name!r}")
    return f"{m.group(1)}[{m.group(2)}]"
```

- [ ] **Step 4: Run; expect pass.**

```bash
python -m pytest tests/test_dispensers_echo.py -v
```

Expected: 6 tests pass.

- [ ] **Step 5: Commit.**

```bash
git add src/iplaid/dispensers/echo.py tests/test_dispensers_echo.py
git commit -m "feat(echo): add well-padding and sample-name helpers"
```

---

### Task E1.3: `EchoDispenser` skeleton — spec + load_plate_specs

**Files:**
- Modify: `src/iplaid/dispensers/echo.py`
- Modify: `tests/test_dispensers_echo.py`

- [ ] **Step 1: Append failing test.**

```python
from iplaid.dispensers.echo import EchoDispenser
from iplaid.dispensers import get_dispenser


def test_echo_dispenser_spec() -> None:
    disp = EchoDispenser()
    assert disp.spec.name == "echo"
    assert disp.spec.min_increment_nL == 2.5
    assert disp.spec.default_sourceplate_type == "384PP_DMSO2"


def test_echo_registered() -> None:
    disp = get_dispenser("echo")
    assert isinstance(disp, EchoDispenser)


def test_echo_load_plate_specs(tmp_path: Path) -> None:
    # Create a minimal data/echo_plate_specs.json under tmp_path
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "echo_plate_specs.json").write_text(
        '{"384PP_DMSO2": {"x_offset": 1050, "y_offset": -1050, "dispense_min_nL": 2.5}}'
    )
    disp = EchoDispenser()
    specs = disp.load_plate_specs(tmp_path)
    assert specs["384PP_DMSO2"]["x_offset"] == 1050
```

- [ ] **Step 2: Run; expect failure.**

```bash
python -m pytest tests/test_dispensers_echo.py::test_echo_dispenser_spec -v
```

- [ ] **Step 3: Append to `src/iplaid/dispensers/echo.py`.**

```python
class EchoDispenser:
    spec = DispenserSpec(
        name="echo",
        display_name="Echo",
        plate_specs_path="echo_plate_specs.json",
        min_increment_nL=2.5,
        default_sourceplate_type="384PP_DMSO2",
        default_target_plate_type="Corning_384w_3784",
    )

    def load_plate_specs(self, project_root: Path) -> dict:
        return json.loads((Path(project_root) / "data" / self.spec.plate_specs_path).read_text())

    # build_protocol, write_protocol, write_liquids, validate_export added in subsequent tasks.


_register(EchoDispenser())
```

- [ ] **Step 4: Run.**

```bash
python -m pytest tests/test_dispensers_echo.py -v
```

Expected: all pass (including the three new ones).

- [ ] **Step 5: Commit.**

```bash
git add src/iplaid/dispensers/echo.py tests/test_dispensers_echo.py
git commit -m "feat(echo): register EchoDispenser with spec and load_plate_specs"
```

---

### Task E1.4: `EchoDispenser.build_protocol`

**Files:**
- Modify: `src/iplaid/dispensers/echo.py`
- Modify: `tests/test_dispensers_echo.py`

- [ ] **Step 1: Append failing test.**

```python
def test_echo_build_protocol_columns_and_format() -> None:
    all_rows = pd.DataFrame({
        "Liquid Name": ["[gemcitabine][1.0]", "[etoposide][10.0]", "[dmso][0.0]"],
        "Source Plate": ["source_dmso", "source_dmso", "source_dmso"],
        "Source Well": ["A1", "A2", "A12"],
        "Target Plate": ["P1", "P1", "P1"],
        "Target Well": ["B02", "B03", "B17"],
        "Volume [uL]": [0.005, 0.0125, 0.05],  # 5.0, 12.5, 50.0 nL
    })
    liquid_table = pd.DataFrame({
        "Liquid Name": ["[gemcitabine][1.0]", "[etoposide][10.0]", "[dmso][0.0]"],
        "Source Plate": ["source_dmso"] * 3,
        "Source Well": ["A1", "A2", "A12"],
    })
    cfg = {
        "sourceplate_type": "384PP_DMSO2",
        "target_plate_type": "Corning_384w_3784",
    }
    source_specs = {"x_offset": 1050, "y_offset": -1050}

    out = EchoDispenser().build_protocol(all_rows, liquid_table, cfg=cfg, source_specs=source_specs)

    assert list(out.columns) == [
        "Sample Name", "Source Plate Name", "Source well",
        "Destination Plate Barcode", "destination well", "Transfer Volume",
        "Source Plate Type", "Destination Plate Type",
        "Destination Well X Offset", "Destination Well Y Offset",
    ]
    assert list(out["Sample Name"]) == ["gemcitabine[1.0]", "etoposide[10.0]", "dmso[0.0]"]
    assert list(out["Source well"]) == ["A01", "A02", "A12"]
    assert list(out["destination well"]) == ["B2", "B3", "B17"]
    assert list(out["Transfer Volume"]) == ["5.0", "12.5", "50.0"]
    assert (out["Source Plate Type"] == "384PP_DMSO2").all()
    assert (out["Destination Well X Offset"] == 1050).all()
```

- [ ] **Step 2: Run; expect failure (`build_protocol` not defined).**

- [ ] **Step 3: Add the method to `EchoDispenser`** in `echo.py`:

```python
    def build_protocol(self, all_rows, liquid_table, *, cfg, source_specs):
        out = pd.DataFrame()
        out["Sample Name"] = all_rows["Liquid Name"].map(_liquid_name_to_sample_name)
        out["Source Plate Name"] = all_rows["Source Plate"]
        out["Source well"] = all_rows["Source Well"].map(_pad_source_well)
        out["Destination Plate Barcode"] = all_rows["Target Plate"]
        out["destination well"] = all_rows["Target Well"].map(_unpad_dest_well)
        # Volume comes in as µL; Echo wants nL formatted as %.1f
        out["Transfer Volume"] = (all_rows["Volume [uL]"].astype(float) * 1000.0).map(lambda v: f"{v:.1f}")
        out["Source Plate Type"] = cfg["sourceplate_type"]
        out["Destination Plate Type"] = cfg["target_plate_type"]
        out["Destination Well X Offset"] = source_specs["x_offset"]
        out["Destination Well Y Offset"] = source_specs["y_offset"]
        return out.reset_index(drop=True)
```

- [ ] **Step 4: Run; expect pass.**

```bash
python -m pytest tests/test_dispensers_echo.py::test_echo_build_protocol_columns_and_format -v
```

- [ ] **Step 5: Commit.**

```bash
git add src/iplaid/dispensers/echo.py tests/test_dispensers_echo.py
git commit -m "feat(echo): build_protocol composes 10-column Echo CSV body"
```

---

### Task E1.5: `EchoDispenser.write_protocol` (encoding + line endings)

**Files:**
- Modify: `src/iplaid/dispensers/echo.py`
- Modify: `tests/test_dispensers_echo.py`

- [ ] **Step 1: Append failing test.**

```python
def test_echo_write_protocol_uses_utf8_no_bom_and_lf(tmp_path: Path) -> None:
    df = pd.DataFrame({
        "Sample Name": ["gemcitabine[1.0]"],
        "Source Plate Name": ["source_dmso"],
        "Source well": ["A01"],
        "Destination Plate Barcode": ["P1"],
        "destination well": ["B2"],
        "Transfer Volume": ["5.0"],
        "Source Plate Type": ["384PP_DMSO2"],
        "Destination Plate Type": ["Corning_384w_3784"],
        "Destination Well X Offset": [1050],
        "Destination Well Y Offset": [-1050],
    })
    out = tmp_path / "echo.csv"
    EchoDispenser().write_protocol(df, out)
    raw = out.read_bytes()
    # No BOM:
    assert not raw.startswith(b"\xef\xbb\xbf")
    # LF only, no CRLF anywhere:
    assert b"\r\n" not in raw
    assert raw.count(b"\n") == 2  # header + 1 row
```

- [ ] **Step 2: Run; expect failure.**

- [ ] **Step 3: Add the method to `EchoDispenser`.**

```python
    def write_protocol(self, protocol_df: pd.DataFrame, out_path: Path) -> None:
        protocol_df.to_csv(out_path, index=False, encoding="utf-8", lineterminator="\n")
```

- [ ] **Step 4: Run; expect pass.**

- [ ] **Step 5: Commit.**

```bash
git commit -am "feat(echo): write_protocol uses utf-8 + LF (no BOM)"
```

---

### Task E1.6: `EchoDispenser.write_liquids` and `validate_export`

**Files:**
- Modify: `src/iplaid/dispensers/echo.py`
- Modify: `tests/test_dispensers_echo.py`

- [ ] **Step 1: Append failing tests.**

```python
def test_echo_write_liquids_round_trip(tmp_path: Path) -> None:
    lt = pd.DataFrame({
        "Liquid Name": ["[gemcitabine][1.0]"],
        "Source Plate": ["SRC_T"],
        "Source Well": ["A1"],
    })
    out = tmp_path / "liquids.csv"
    EchoDispenser().write_liquids(lt, out)
    back = pd.read_csv(out)
    assert list(back["Liquid Name"]) == ["[gemcitabine][1.0]"]


def test_echo_validate_export_accepts_good_file(tmp_path: Path) -> None:
    df = pd.DataFrame({
        "Sample Name": ["gemcitabine[1.0]"],
        "Source Plate Name": ["source_dmso"],
        "Source well": ["A01"],
        "Destination Plate Barcode": ["P1"],
        "destination well": ["B2"],
        "Transfer Volume": ["5.0"],
        "Source Plate Type": ["384PP_DMSO2"],
        "Destination Plate Type": ["Corning_384w_3784"],
        "Destination Well X Offset": [1050],
        "Destination Well Y Offset": [-1050],
    })
    out = tmp_path / "echo.csv"
    EchoDispenser().write_protocol(df, out)
    preview, idx = EchoDispenser().validate_export(out, protocol_name="P1", user_name="U")
    assert idx == 0
    assert len(preview) == 1


def test_echo_validate_export_rejects_non_increment(tmp_path: Path) -> None:
    df = pd.DataFrame({
        "Sample Name": ["x[1.0]"],
        "Source Plate Name": ["s"],
        "Source well": ["A01"],
        "Destination Plate Barcode": ["P"],
        "destination well": ["B2"],
        "Transfer Volume": ["12.7"],  # NOT a multiple of 2.5
        "Source Plate Type": ["384PP_DMSO2"],
        "Destination Plate Type": ["Corning_384w_3784"],
        "Destination Well X Offset": [1050],
        "Destination Well Y Offset": [-1050],
    })
    out = tmp_path / "bad.csv"
    EchoDispenser().write_protocol(df, out)
    with pytest.raises(ValueError, match="non-2.5"):
        EchoDispenser().validate_export(out, protocol_name="P", user_name="U")


def test_echo_validate_export_rejects_unpadded_source(tmp_path: Path) -> None:
    df = pd.DataFrame({
        "Sample Name": ["x[1.0]"],
        "Source Plate Name": ["s"],
        "Source well": ["A1"],  # NOT zero-padded
        "Destination Plate Barcode": ["P"],
        "destination well": ["B2"],
        "Transfer Volume": ["5.0"],
        "Source Plate Type": ["384PP_DMSO2"],
        "Destination Plate Type": ["Corning_384w_3784"],
        "Destination Well X Offset": [1050],
        "Destination Well Y Offset": [-1050],
    })
    out = tmp_path / "bad2.csv"
    EchoDispenser().write_protocol(df, out)
    with pytest.raises(ValueError, match="zero-padded"):
        EchoDispenser().validate_export(out, protocol_name="P", user_name="U")
```

- [ ] **Step 2: Run; expect failures.**

- [ ] **Step 3: Add the methods.**

```python
    def write_liquids(self, liquid_table_export: pd.DataFrame, out_path: Path) -> None:
        liquid_table_export.to_csv(out_path, index=False)

    def validate_export(
        self,
        out_path: Path,
        *,
        protocol_name: str,
        user_name: str,
    ) -> tuple[pd.DataFrame, int]:
        df = pd.read_csv(out_path, encoding="utf-8")
        expected_cols = [
            "Sample Name", "Source Plate Name", "Source well",
            "Destination Plate Barcode", "destination well", "Transfer Volume",
            "Source Plate Type", "Destination Plate Type",
            "Destination Well X Offset", "Destination Well Y Offset",
        ]
        if list(df.columns) != expected_cols:
            raise ValueError(f"Echo CSV header mismatch: got {list(df.columns)}")
        if len(df) == 0:
            raise ValueError("Echo CSV has no dispense rows")
        vols = pd.to_numeric(df["Transfer Volume"], errors="raise")
        bad_vol = df[((vols % 2.5).round(6) != 0)]
        if len(bad_vol) > 0:
            raise ValueError(f"{len(bad_vol)} rows have non-2.5 nL volumes")
        if not df["Source well"].astype(str).str.match(r"^[A-Z]\d{2}$").all():
            raise ValueError("Source wells must be 2-digit zero-padded ([A-Z]\\d{2})")
        if not df["destination well"].astype(str).str.match(r"^[A-Z]\d+$").all():
            raise ValueError("Destination wells malformed")
        if df.isna().any().any():
            raise ValueError("Echo CSV contains NaN")
        return df.head(20), 0
```

- [ ] **Step 4: Run; expect pass.**

- [ ] **Step 5: Commit.**

```bash
git commit -am "feat(echo): write_liquids + validate_export with strict format checks"
```

---

### Task E1.7: `apply_dispenser_increment` rounding step

**Files:**
- Modify: `src/iplaid/normalization.py`
- Create: `tests/test_normalization_increment.py`

- [ ] **Step 1: Write failing tests.**

```python
"""Tests for dispenser-increment rounding."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from iplaid.normalization import apply_dispenser_increment


def test_increment_zero_is_noop() -> None:
    df = pd.DataFrame({
        "Volume [uL]": [0.0042, 0.012],
        "stock_conc_mM": [10.0, 1.0],
        "well_vol_uL": [40.0, 40.0],
        "CONCuM": [1.05, 0.3],
    })
    out = apply_dispenser_increment(df, increment_nL=0)
    pd.testing.assert_frame_equal(out, df)


def test_increment_25nl_rounds_volume() -> None:
    df = pd.DataFrame({
        "Volume [uL]": [0.004, 0.012, 0.0625],   # 4.0, 12.0, 62.5 nL
        "stock_conc_mM": [10.0, 10.0, 10.0],
        "well_vol_uL": [40.0, 40.0, 40.0],
        "CONCuM": [1.0, 3.0, 15.625],
    })
    out = apply_dispenser_increment(df, increment_nL=2.5)
    # 4.0 -> 5.0, 12.0 -> 12.5, 62.5 -> 62.5 (already a multiple)
    assert list((out["Volume [uL]"] * 1000).round(2)) == [5.0, 12.5, 62.5]


def test_increment_back_calculates_concum() -> None:
    df = pd.DataFrame({
        "Volume [uL]": [0.004],     # 4.0 nL requested -> rounds to 5.0 nL
        "stock_conc_mM": [10.0],
        "well_vol_uL": [40.0],
        "CONCuM": [1.0],            # requested
    })
    out = apply_dispenser_increment(df, increment_nL=2.5)
    # achieved CONCuM = (5.0 nL * 10 mM * 1000) / (40 uL * 1000) = 1.25 uM
    assert round(out["CONCuM"].iloc[0], 4) == 1.25
    assert out["CONCuM_requested"].iloc[0] == 1.0
    assert round(out["Volume_nL_unrounded"].iloc[0], 4) == 4.0


def test_increment_skips_solvent_rows_with_zero_stock() -> None:
    df = pd.DataFrame({
        "Volume [uL]": [0.0125],        # 12.5 nL solvent topup
        "stock_conc_mM": [0.0],         # solvent
        "well_vol_uL": [40.0],
        "CONCuM": [0.0],
    })
    out = apply_dispenser_increment(df, increment_nL=2.5)
    assert "CONCuM_requested" not in out.columns or pd.isna(out["CONCuM_requested"].iloc[0])
    # Volume still gets rounded (12.5 nL is already a multiple, unchanged):
    assert round(out["Volume [uL]"].iloc[0] * 1000, 2) == 12.5
```

- [ ] **Step 2: Run; expect ImportError.**

- [ ] **Step 3: Add to `src/iplaid/normalization.py`** (append at the end).

```python
def apply_dispenser_increment(df: pd.DataFrame, increment_nL: float) -> pd.DataFrame:
    """Round transfer volumes to the dispenser's increment and back-calc achieved CONCuM.

    No-op when increment_nL == 0 (iDOT). For Echo (2.5 nL), each compound row's
    Volume [uL] is rounded to the nearest 2.5 nL and CONCuM is recomputed from the
    rounded volume so iMETA reflects what was actually dispensed. Solvent rows
    (stock_conc_mM == 0) get volume rounding only — no CONCuM rewrite.
    """
    if increment_nL <= 0:
        return df

    df = df.copy()
    vol_nL = df["Volume [uL]"].astype(float) * 1000.0
    rounded_nL = (vol_nL / increment_nL).round() * increment_nL
    df["Volume_nL_unrounded"] = vol_nL
    df["Volume [uL]"] = rounded_nL / 1000.0

    has_stock = df["stock_conc_mM"].fillna(0) > 0
    if has_stock.any():
        df.loc[has_stock, "CONCuM_requested"] = df.loc[has_stock, "CONCuM"]
        df.loc[has_stock, "CONCuM"] = (
            df.loc[has_stock, "Volume [uL]"] * df.loc[has_stock, "stock_conc_mM"]
            * 1000.0 / df.loc[has_stock, "well_vol_uL"]
        )

        # Warn (do NOT raise) if any well's deviation exceeds 5%
        deviation_pct = (
            (df.loc[has_stock, "CONCuM"] - df.loc[has_stock, "CONCuM_requested"]).abs()
            / df.loc[has_stock, "CONCuM_requested"].replace(0, pd.NA)
            * 100
        )
        n_over = int((deviation_pct > 5.0).sum())
        if n_over > 0:
            print(
                f"⚠ {n_over} wells have >5% concentration deviation after rounding "
                f"to {increment_nL} nL increments. See CONCuM_requested in iMETA."
            )

    return df
```

- [ ] **Step 4: Run; expect pass.**

```bash
python -m pytest tests/test_normalization_increment.py -v
```

- [ ] **Step 5: Commit.**

```bash
git add src/iplaid/normalization.py tests/test_normalization_increment.py
git commit -m "feat(normalization): add apply_dispenser_increment for Echo 2.5 nL rounding"
```

---

### Task E1.8: Wire Echo into `pipeline.py`

**Files:**
- Modify: `src/iplaid/pipeline.py`

- [ ] **Step 1: Add the increment step to `_run_pipeline_with_resolved_inputs`.** Locate the line that imports normalization functions; ensure `apply_dispenser_increment` is imported:

```python
from .normalization import (
    add_target_and_volume_columns,
    enforce_solvent_volume_cap,
    normalize_solvent_topup,
    apply_dispenser_increment,
)
```

Locate the section that does `add_target_and_volume_columns(...)` — directly after that call (and before `enforce_solvent_volume_cap`), insert:

```python
# Dispenser-specific volume rounding (no-op for iDOT).
if disp.spec.min_increment_nL > 0:
    df = apply_dispenser_increment(df, disp.spec.min_increment_nL)
```

- [ ] **Step 2: Re-run the iDOT golden suite to confirm the no-op branch is truly no-op.**

```bash
python -m pytest tests/test_pipeline.py -v
```

Expected: all iDOT goldens still pass byte-equal.

- [ ] **Step 3: Commit.**

```bash
git commit -am "feat(pipeline): apply dispenser increment after volume calc (no-op for iDOT)"
```

---

### Task E1.9: Echo end-to-end smoke test

**Files:**
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Add the smoke test.**

```python
def test_echo_smoke_produces_valid_csv(tmp_path: Path) -> None:
    """Run the full pipeline with dispenser='echo' and assert the output validates."""
    src = GOLDEN_DIR / "idot_basic"
    work = tmp_path / "echo_smoke"
    work.mkdir()
    shutil.copy(src / "layout.csv", work / "layout.csv")
    shutil.copy(src / "meta.csv", work / "meta.csv")
    cfg = json.loads((src / "config.json").read_text())
    cfg["dispenser"] = "echo"
    cfg["sourceplate_type"] = "384PP_DMSO2"
    cfg["target_plate_type"] = "Corning_384w_3784"
    cfg["working_volume_ul"] = 50  # match Echo legacy convention
    out_dir = work / "out"
    out_dir.mkdir()

    result = run_pipeline_with_inputs(
        config=cfg,
        layout_path=work / "layout.csv",
        meta_path=work / "meta.csv",
        output_dir=out_dir,
        include_source_prep=False,
    )
    out_path = Path(result["paths"]["out_idot"])  # path key is shared; file is the Echo CSV
    assert out_path.exists()
    df = pd.read_csv(out_path)
    assert len(df.columns) == 10
    assert df.columns[0] == "Sample Name"
    assert df.columns[5] == "Transfer Volume"
    # Every transfer is a multiple of 2.5 nL:
    vols = pd.to_numeric(df["Transfer Volume"])
    assert ((vols % 2.5).round(6) == 0).all()
```

- [ ] **Step 2: Run; expect pass (Echo registered, pipeline routes through it).**

```bash
python -m pytest tests/test_pipeline.py::test_echo_smoke_produces_valid_csv -v
```

Expected: pass. If it fails because `inputs/meta_example.csv` doesn't include `384PP_DMSO2`-compatible compounds, override the highest_stock to make all rows feasible — adjust the meta CSV in the fixture as needed (the fix lives in `tests/golden/idot_basic/meta.csv`).

- [ ] **Step 3: Commit.**

```bash
git commit -am "test(pipeline): add Echo smoke test"
```

---

### Task E1.10: Echo golden file regression

**Files:**
- Create: `tests/golden/echo_basic/layout.csv`
- Create: `tests/golden/echo_basic/meta.csv`
- Create: `tests/golden/echo_basic/config.json`
- Create: `tests/golden/echo_basic/expected_protocol.csv`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Copy the iDOT fixture inputs and adjust config for Echo.**

```bash
mkdir -p tests/golden/echo_basic
cp tests/golden/idot_basic/layout.csv tests/golden/echo_basic/layout.csv
cp tests/golden/idot_basic/meta.csv tests/golden/echo_basic/meta.csv
```

- [ ] **Step 2: Write `tests/golden/echo_basic/config.json`** mirroring the iDOT one but with Echo settings:

```json
{
  "user_name": "GoldenTest",
  "protocol_name": "ECHO_BASIC_GOLDEN",
  "layout_file": "layout.csv",
  "meta_file": "meta.csv",
  "dispenser": "echo",
  "sourceplate_type": "384PP_DMSO2",
  "target_plate_type": "Corning_384w_3784",
  "working_volume_ul": 50,
  "max_dmso_pct": 0.1,
  "source_prep_overage_pct": 0.30,
  "min_pipette_volume_uL": 1.0,
  "dilution_solvent": "DMSO",
  "source_well_fill_pct": 0.70,
  "standard_prep_volume_uL": 1000.0,
  "output_timestamp_format": "FROZEN-TIMESTAMP"
}
```

- [ ] **Step 3: Add the failing test.**

```python
def test_echo_basic_byte_equal(tmp_path: Path) -> None:
    result = _run_golden("echo_basic", tmp_path)
    expected = (GOLDEN_DIR / "echo_basic" / "expected_protocol.csv").read_bytes()
    actual = Path(result["paths"]["out_idot"]).read_bytes()
    assert actual == expected, "Echo protocol CSV diverged from golden"
```

- [ ] **Step 4: Run; expect failure (no expected file).**

- [ ] **Step 5: Capture the golden.**

```bash
python -c "
import json, shutil, sys
from pathlib import Path
sys.path.insert(0, 'src')
from iplaid.pipeline import run_pipeline_with_inputs

src = Path('tests/golden/echo_basic')
work = Path('/tmp/echo_capture'); work.mkdir(exist_ok=True)
shutil.copy(src/'layout.csv', work/'layout.csv')
shutil.copy(src/'meta.csv', work/'meta.csv')
cfg = json.loads((src/'config.json').read_text())
out = work/'out'; out.mkdir(exist_ok=True)
r = run_pipeline_with_inputs(config=cfg, layout_path=work/'layout.csv', meta_path=work/'meta.csv', output_dir=out, include_source_prep=False)
shutil.copy(r['paths']['out_idot'], src/'expected_protocol.csv')
print('captured to', src)
"
```

- [ ] **Step 6: Re-run; expect pass.**

```bash
python -m pytest tests/test_pipeline.py::test_echo_basic_byte_equal -v
```

- [ ] **Step 7: Commit.**

```bash
git add tests/golden/echo_basic/ tests/test_pipeline.py
git commit -m "test(pipeline): lock Echo byte-equal regression fence"
```

**Phase E1 complete.** Echo dispenser produces a vendor-correct CSV with regression tests in place.

---

## Phase E2 — Source-plate-import (works for both backends)

### Task E2.1: Extend `build_liquid_table` to accept `existing_layout`

**Files:**
- Modify: `src/iplaid/output.py`
- Create: `tests/test_source_plate_import.py`

- [ ] **Step 1: Write failing tests.**

```python
"""Tests for user-supplied source-plate layout import."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from iplaid.dispensers.base import SourceLayoutError
from iplaid.output import build_liquid_table


def _all_rows() -> pd.DataFrame:
    return pd.DataFrame({
        "Target Plate": ["P1"] * 3,
        "Target Well": ["A1", "A2", "A3"],
        "Liquid Name": ["[gemcitabine][1.0]", "[etoposide][10.0]", "[dmso][0.0]"],
        "Volume [uL]": [0.005, 0.0125, 0.01],
    })


def test_build_liquid_table_default_auto_assigns() -> None:
    lt, lt_export = build_liquid_table(_all_rows(), "PROTO")
    # Auto-assign produces wells starting at A1
    assert lt_export["Source Well"].iloc[0] == "A1"


def test_build_liquid_table_uses_existing_layout() -> None:
    layout = pd.DataFrame({
        "Source Well": ["A07", "A10", "A12"],
        "Liquid Name": ["[gemcitabine][1.0]", "[etoposide][10.0]", "[dmso][0.0]"],
    })
    lt, lt_export = build_liquid_table(_all_rows(), "PROTO", existing_layout=layout)
    mapping = dict(zip(lt_export["Liquid Name"], lt_export["Source Well"]))
    assert mapping["[gemcitabine][1.0]"] == "A07"
    assert mapping["[etoposide][10.0]"] == "A10"
    assert mapping["[dmso][0.0]"] == "A12"


def test_build_liquid_table_rejects_missing_liquid() -> None:
    layout = pd.DataFrame({
        "Source Well": ["A07"],
        "Liquid Name": ["[gemcitabine][1.0]"],  # missing etoposide and dmso
    })
    with pytest.raises(SourceLayoutError, match="missing"):
        build_liquid_table(_all_rows(), "PROTO", existing_layout=layout)


def test_build_liquid_table_rejects_duplicate_wells() -> None:
    layout = pd.DataFrame({
        "Source Well": ["A07", "A07", "A12"],
        "Liquid Name": ["[gemcitabine][1.0]", "[etoposide][10.0]", "[dmso][0.0]"],
    })
    with pytest.raises(SourceLayoutError, match="duplicate"):
        build_liquid_table(_all_rows(), "PROTO", existing_layout=layout)


def test_build_liquid_table_layout_unused_entries_warn_not_fail(capsys) -> None:
    layout = pd.DataFrame({
        "Source Well": ["A07", "A10", "A12", "A15"],   # A15 is unused
        "Liquid Name": ["[gemcitabine][1.0]", "[etoposide][10.0]", "[dmso][0.0]", "[unused][5.0]"],
    })
    lt, _ = build_liquid_table(_all_rows(), "PROTO", existing_layout=layout)
    captured = capsys.readouterr()
    assert "unused" in captured.out.lower() or "1 layout entr" in captured.out.lower()
```

- [ ] **Step 2: Run; expect failure (`existing_layout` kwarg unknown).**

- [ ] **Step 3: Modify `src/iplaid/output.py::build_liquid_table`.** Replace the existing function signature and body:

```python
from .dispensers.base import SourceLayoutError  # add to top-of-file imports


def build_liquid_table(
    all_rows: pd.DataFrame,
    protocol_name: str,
    *,
    existing_layout: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the liquid table mapping each unique Liquid Name to a source well.

    If existing_layout is None: auto-assign wells in deterministic order (current behavior).
    If existing_layout is provided: validate completeness and map source wells from it.
    """
    liquid_table = all_rows[["Liquid Name"]].drop_duplicates().copy()

    liquid_table[["compound", "stock_str"]] = liquid_table["Liquid Name"].str.extract(
        r"^\[(.*?)\]\[(.*?)\]$"
    )
    bad = liquid_table.loc[liquid_table[["compound", "stock_str"]].isna().any(axis=1), "Liquid Name"]
    if len(bad) > 0:
        raise ValueError(f"Liquid Name not in expected format [Compound][Stock]:\n{bad.to_list()}")

    liquid_table["stock_mM"] = pd.to_numeric(liquid_table["stock_str"], errors="raise")
    liquid_table["is_control_liquid"] = liquid_table["stock_mM"] == 0
    liquid_table["sort_group"] = (~liquid_table["is_control_liquid"]).astype(int)

    liquid_table = liquid_table.sort_values(
        ["sort_group", "compound", "stock_mM", "Liquid Name"],
        kind="mergesort",
    ).reset_index(drop=True)

    if existing_layout is None:
        # Auto-assign (existing behavior)
        liquid_table["Source Plate"] = f"SRC_{protocol_name}"
        avail = wells_96()
        if len(liquid_table) > len(avail):
            raise ValueError(
                f"Too many unique liquids ({len(liquid_table)}) for one source plate ({len(avail)} wells)."
            )
        liquid_table["Source Well"] = avail[: len(liquid_table)]
    else:
        # Validate the supplied layout and map wells from it.
        if "Source Well" not in existing_layout.columns or "Liquid Name" not in existing_layout.columns:
            raise SourceLayoutError(
                "existing_layout must have columns 'Source Well' and 'Liquid Name'"
            )
        layout = existing_layout.copy()
        if layout["Source Well"].duplicated().any():
            dups = layout.loc[layout["Source Well"].duplicated(keep=False), "Source Well"].tolist()
            raise SourceLayoutError(f"existing_layout has duplicate Source Wells: {dups}")

        required = set(liquid_table["Liquid Name"])
        provided = set(layout["Liquid Name"])
        missing = sorted(required - provided)
        if missing:
            raise SourceLayoutError(f"existing_layout missing required liquids: {missing}")

        unused = sorted(provided - required)
        if unused:
            print(f"⚠ existing_layout has {len(unused)} unused entr{'y' if len(unused) == 1 else 'ies'}: {unused}")

        # Map source wells/plate from the layout
        well_map = dict(zip(layout["Liquid Name"], layout["Source Well"]))
        liquid_table["Source Well"] = liquid_table["Liquid Name"].map(well_map)
        if "Source Plate" in layout.columns:
            plate_map = dict(zip(layout["Liquid Name"], layout["Source Plate"]))
            liquid_table["Source Plate"] = liquid_table["Liquid Name"].map(plate_map)
        else:
            liquid_table["Source Plate"] = f"SRC_{protocol_name}"

    liquid_table_export = liquid_table[["Liquid Name", "Source Plate", "Source Well"]].copy()
    return liquid_table, liquid_table_export
```

- [ ] **Step 4: Run; expect pass.**

```bash
python -m pytest tests/test_source_plate_import.py tests/test_pipeline.py -v
```

Expected: all pass. The iDOT and Echo goldens MUST still pass byte-equal — the auto-assign path is unchanged because `existing_layout` defaults to `None`.

- [ ] **Step 5: Commit.**

```bash
git add src/iplaid/output.py tests/test_source_plate_import.py
git commit -m "feat(output): build_liquid_table supports user-supplied source layout"
```

---

### Task E2.2: Plumb `source_layout_path` through the pipeline

**Files:**
- Modify: `src/iplaid/pipeline.py`

- [ ] **Step 1: Add `source_layout_path` kwarg to `run_pipeline_with_inputs`.**

```python
def run_pipeline_with_inputs(
    *,
    config: dict,
    layout_path: str | Path,
    meta_path: str | Path,
    output_dir: str | Path,
    include_source_prep: bool = True,
    project_root: str | Path | None = None,
    plate_specs_path: str | Path | None = None,
    source_layout_path: str | Path | None = None,   # NEW
):
```

In the body, before calling `_run_pipeline_with_resolved_inputs`, load the layout if provided:

```python
existing_layout_df = None
if source_layout_path is not None:
    existing_layout_df = pd.read_csv(source_layout_path)
```

Pass `existing_layout=existing_layout_df` into `_run_pipeline_with_resolved_inputs`.

- [ ] **Step 2: Update `_run_pipeline_with_resolved_inputs`** to accept and forward the layout.

Change the signature to:
```python
def _run_pipeline_with_resolved_inputs(
    *,
    root: Path,
    cfg: dict,
    paths: dict,
    include_source_prep: bool,
    existing_layout: pd.DataFrame | None = None,
):
```

Locate the call to `build_liquid_table` and update:

```python
liquid_table, liquid_table_export = build_liquid_table(
    all_rows,
    str(cfg["protocol_name"]),
    existing_layout=existing_layout,
)
```

Update both `run_pipeline` and `run_pipeline_with_inputs` to pass `existing_layout=existing_layout_df` (or `None`) into the resolved-inputs call.

- [ ] **Step 3: Add a pipeline-level test.**

In `tests/test_source_plate_import.py`, append:

```python
import json
import shutil


def test_pipeline_with_existing_source_layout_idot(tmp_path: Path) -> None:
    """Round-trip: capture iDOT goldens layout, then re-run with it as input → byte-equal."""
    from iplaid.pipeline import run_pipeline_with_inputs

    src = Path(__file__).parent / "golden" / "idot_basic"
    # Use the captured liquids file as a source layout
    layout_csv = src / "expected_liquids.csv"  # has Liquid Name, Source Plate, Source Well

    work = tmp_path / "with_layout"
    work.mkdir()
    shutil.copy(src / "layout.csv", work / "layout.csv")
    shutil.copy(src / "meta.csv", work / "meta.csv")
    cfg = json.loads((src / "config.json").read_text())
    out_dir = work / "out"
    out_dir.mkdir()
    r = run_pipeline_with_inputs(
        config=cfg,
        layout_path=work / "layout.csv",
        meta_path=work / "meta.csv",
        output_dir=out_dir,
        include_source_prep=False,
        source_layout_path=layout_csv,
    )
    expected = (src / "expected_protocol.csv").read_bytes()
    assert Path(r["paths"]["out_idot"]).read_bytes() == expected
```

- [ ] **Step 4: Run.**

```bash
python -m pytest tests/test_source_plate_import.py tests/test_pipeline.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit.**

```bash
git commit -am "feat(pipeline): plumb source_layout_path through run_pipeline_with_inputs"
```

---

### Task E2.3: Echo + source-layout golden

**Files:**
- Create: `tests/golden/echo_with_layout/`
- Modify: `tests/test_source_plate_import.py`

- [ ] **Step 1: Copy echo_basic and add a layout CSV.**

```bash
cp -r tests/golden/echo_basic tests/golden/echo_with_layout
```

- [ ] **Step 2: Generate a `source_layout.csv`** by running echo_basic once and renaming the liquids output, OR write one by hand. The hand-written approach is more reliable:

After running the echo_basic pipeline once (you already did this in E1.10), inspect `tests/golden/echo_basic/expected_protocol.csv` and grab the unique `(Source Plate Name, Source well)` pairs. Build:

```bash
python -c "
import pandas as pd
from pathlib import Path
src = Path('tests/golden/echo_basic/expected_protocol.csv')
df = pd.read_csv(src)
layout = df[['Sample Name', 'Source Plate Name', 'Source well']].drop_duplicates()
# Convert Sample Name 'gemcitabine[1.0]' back to Liquid Name '[gemcitabine][1.0]'
layout['Liquid Name'] = layout['Sample Name'].str.replace(r'^([^\[]+)\[(.+)\]$', r'[\1][\2]', regex=True)
layout = layout.rename(columns={'Source Plate Name': 'Source Plate', 'Source well': 'Source Well'})
layout = layout[['Liquid Name', 'Source Plate', 'Source Well']]
layout.to_csv('tests/golden/echo_with_layout/source_layout.csv', index=False)
print(layout)
"
```

- [ ] **Step 3: Add the test.**

```python
def test_echo_with_supplied_layout_byte_equal(tmp_path: Path) -> None:
    from iplaid.pipeline import run_pipeline_with_inputs

    src = Path(__file__).parent / "golden" / "echo_with_layout"
    work = tmp_path / "echo_layout"
    work.mkdir()
    shutil.copy(src / "layout.csv", work / "layout.csv")
    shutil.copy(src / "meta.csv", work / "meta.csv")
    cfg = json.loads((src / "config.json").read_text())
    out_dir = work / "out"
    out_dir.mkdir()
    r = run_pipeline_with_inputs(
        config=cfg,
        layout_path=work / "layout.csv",
        meta_path=work / "meta.csv",
        output_dir=out_dir,
        include_source_prep=False,
        source_layout_path=src / "source_layout.csv",
    )
    expected = (src / "expected_protocol.csv").read_bytes()
    assert Path(r["paths"]["out_idot"]).read_bytes() == expected
```

- [ ] **Step 4: Run.**

```bash
python -m pytest tests/test_source_plate_import.py::test_echo_with_supplied_layout_byte_equal -v
```

Expected: pass (the supplied layout matches the auto-assignment for this fixture, so the output is byte-identical to echo_basic).

- [ ] **Step 5: Commit.**

```bash
git add tests/golden/echo_with_layout/ tests/test_source_plate_import.py
git commit -m "test(echo): add supplied-layout golden"
```

**Phase E2 complete.** Source-plate-import works for both backends.

---

## Phase U — UI changes

### Task U1: Add `dispenser` to `RunConfigModel`

**Files:**
- Modify: `backend/app/models.py`

- [ ] **Step 1: Add the field.** Locate `RunConfigModel` (around line 116) and add after `target_plate_type`:

```python
    dispenser: Literal["idot", "echo"] = Field(default="idot")
    source_layout_file: Optional[str] = Field(default=None)
```

Ensure `Literal` and `Optional` are imported at the top of the file (they may already be).

- [ ] **Step 2: Run backend tests if any exist.**

```bash
python -m pytest tests/ -v
```

Expected: all pass (no behavior change yet — field defaults preserve current shape).

- [ ] **Step 3: Commit.**

```bash
git commit -am "feat(api): add dispenser and source_layout_file fields to RunConfigModel"
```

---

### Task U2: Bootstrap endpoint exposes dispenser metadata

**Files:**
- Modify: `backend/app/main.py` (or wherever `/bootstrap` is defined — search if unsure: `grep -rn "sourcePlateTypes\|bootstrap" backend/app`)

- [ ] **Step 1: Locate the endpoint that returns plate types.** Use:

```bash
grep -rn "source_plate_specs\|sourcePlateTypes\|/bootstrap" backend/app
```

Note the file and function (likely `main.py`).

- [ ] **Step 2: Extend the response.** Modify the endpoint handler so the JSON response gains:

```python
from iplaid.dispensers import list_dispensers

# Inside the handler (pseudocode — adapt to actual code):
dispensers = list_dispensers()
plate_types_by_dispenser = {}
for d in dispensers:
    specs_path = Path(project_root) / "data" / d.plate_specs_path
    plate_types_by_dispenser[d.name] = list(json.loads(specs_path.read_text()).keys())

response["dispensers"] = [
    {"name": d.name, "display_name": d.display_name, "default_sourceplate_type": d.default_sourceplate_type}
    for d in dispensers
]
response["plate_types_by_dispenser"] = plate_types_by_dispenser
# Keep the legacy "sourcePlateTypes" field equal to the iDOT list for backwards compat.
```

- [ ] **Step 3: Smoke-test by starting the backend and curling the endpoint.**

```bash
# In a separate terminal:
docker compose up backend
# Then:
curl -s http://127.0.0.1:8000/bootstrap | python -m json.tool | head -40
```

Expected: response includes `dispensers` and `plate_types_by_dispenser` arrays.

- [ ] **Step 4: Commit.**

```bash
git commit -am "feat(api): /bootstrap exposes dispensers and plate_types_by_dispenser"
```

---

### Task U3: Frontend types

**Files:**
- Modify: `frontend/src/types.ts`

- [ ] **Step 1: Extend `RunConfig` and `BootstrapResponse`.**

```ts
export interface RunConfig {
  // ...existing fields...
  dispenser: "idot" | "echo";
  source_layout_file?: string | null;
}

export interface DispenserMeta {
  name: string;
  display_name: string;
  default_sourceplate_type: string;
}

export interface BootstrapResponse {
  // ...existing fields...
  dispensers: DispenserMeta[];
  plate_types_by_dispenser: Record<string, string[]>;
}
```

- [ ] **Step 2: TypeScript-compile-check.**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 0 errors. If errors surface, they likely mean other files reference the old `BootstrapResponse` shape — fix by passing through.

- [ ] **Step 3: Commit.**

```bash
git commit -am "feat(types): RunConfig.dispenser and BootstrapResponse dispenser fields"
```

---

### Task U4: workbenchState — defaults + reset on dispenser change

**Files:**
- Modify: `frontend/src/workbenchState.tsx`

- [ ] **Step 1: Locate the config initial state.** Find the default for `sourceplate_type` and add `dispenser: "idot"` and `source_layout_file: null` next to it.

- [ ] **Step 2: Locate the config-change handler `onConfigChange`.** Add a special case for `dispenser`:

```ts
const onConfigChange = (key: keyof RunConfig, value: any) => {
  if (key === "dispenser") {
    const newDisp = value as "idot" | "echo";
    const dispMeta = bootstrap.dispensers.find(d => d.name === newDisp);
    setConfig(prev => ({
      ...prev,
      dispenser: newDisp,
      sourceplate_type: dispMeta?.default_sourceplate_type ?? prev.sourceplate_type,
      source_layout_file: null,  // clear stale layout when switching dispensers
    }));
    return;
  }
  setConfig(prev => ({ ...prev, [key]: value }));
};
```

(Adapt the exact prop names to the existing code — this is the intent.)

- [ ] **Step 3: tsc-check.**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit.**

```bash
git commit -am "feat(workbench): reset sourceplate_type and source_layout_file on dispenser change"
```

---

### Task U5: RunConfigPanel — dispenser dropdown + dependent plate options

**Files:**
- Modify: `frontend/src/components/workbench/RunConfigPanel.tsx`

- [ ] **Step 1: Insert the Dispenser dropdown directly above the existing Source plate dropdown** (around line 82):

```tsx
<label>
  <span>Dispenser</span>
  <select
    value={config.dispenser}
    onChange={(e) => onConfigChange("dispenser", e.target.value)}
  >
    {bootstrap.dispensers.map(d => (
      <option key={d.name} value={d.name}>{d.display_name}</option>
    ))}
  </select>
</label>
```

- [ ] **Step 2: Update the existing Source plate dropdown** to use `bootstrap.plate_types_by_dispenser[config.dispenser]` instead of `bootstrap.sourcePlateTypes`:

```tsx
<label>
  <span>Source plate</span>
  <select
    value={config.sourceplate_type}
    onChange={(e) => onConfigChange("sourceplate_type", e.target.value)}
  >
    {(bootstrap.plate_types_by_dispenser[config.dispenser] ?? bootstrap.sourcePlateTypes).map((plateType) => (
      <option key={plateType} value={plateType}>{plateType}</option>
    ))}
  </select>
</label>
```

- [ ] **Step 3: tsc-check + manual UI check.**

```bash
cd frontend && npx tsc --noEmit
docker compose up
# Open http://127.0.0.1:8000 in a browser, switch the Dispenser dropdown, observe the Source plate dropdown's options change.
```

- [ ] **Step 4: Commit.**

```bash
git commit -am "feat(ui): add Dispenser dropdown; Source plate options follow dispenser"
```

---

### Task U6: Optional source-layout file picker

**Files:**
- Modify: `frontend/src/components/workbench/RunConfigPanel.tsx`
- Modify: `backend/app/designer.py` (or wherever the run endpoint lives)

- [ ] **Step 1: Add the file input to RunConfigPanel** below the existing layout/meta uploads:

```tsx
<label>
  <span>Source plate layout (optional)</span>
  <input
    type="file"
    accept=".csv"
    onChange={async (e) => {
      const file = e.target.files?.[0];
      if (!file) { onConfigChange("source_layout_file", null); return; }
      const filename = await uploadFile(file, "source_layout");  // existing upload helper
      onConfigChange("source_layout_file", filename);
    }}
  />
</label>
```

(Use the project's existing file-upload helper — if uploads currently use a single `uploadFile(file, kind)` signature, follow the same pattern.)

- [ ] **Step 2: In `backend/app/designer.py`** (or the run endpoint), pass `source_layout_path` through to `run_pipeline_with_inputs`:

```python
source_layout_path = None
if config.source_layout_file:
    source_layout_path = Path(uploads_dir) / config.source_layout_file

result = run_pipeline_with_inputs(
    config=config.model_dump(),
    layout_path=...,
    meta_path=...,
    output_dir=...,
    source_layout_path=source_layout_path,
)
```

- [ ] **Step 3: Manual UI test.** Upload a CSV, run a job, verify the Source Well column in the output liquids.csv matches the uploaded layout.

- [ ] **Step 4: Commit.**

```bash
git commit -am "feat(ui): optional source-plate layout upload routes through pipeline"
```

**Phase U complete.** UI exposes Dispenser selection and optional source-layout import.

---

## Phase B — Bench validation (manual; no code)

### Task B1: iDOT regression bench run

- [ ] **Step 1:** Pick a recent iDOT run from `backend/data/jobs/`. Re-run it through the new code with the same inputs.
- [ ] **Step 2:** `diff -q` the new outputs against the original. Expected: empty diff.
- [ ] **Step 3:** Load the protocol on the actual iDOT machine via the lab's normal procedure. Confirm it runs to completion.

### Task B2: Echo bench run

- [ ] **Step 1:** Use a colo8-style PLAID layout the lab already trusts.
- [ ] **Step 2:** Run through iPLAID with `dispenser: "echo"`. Inspect the Echo CSV in a text editor; verify the 10 columns, 2.5 nL multiples, well padding asymmetry.
- [ ] **Step 3:** Load on the Echo machine. Confirm it accepts the file and runs to completion.

### Task B3: Source-layout bench run

- [ ] **Step 1:** Take a pre-prepared physical Echo source plate the lab already has. Translate its layout to a CSV (`Liquid Name, Source Plate, Source Well`).
- [ ] **Step 2:** Run iPLAID with that CSV uploaded. Confirm the Echo output references the wells you specified, not auto-assigned ones.

---

## Self-review

**Spec coverage check** against `docs/superpowers/specs/2026-05-02-echo-dispenser-design.md`:

- §1 Goal — covered by Phases M+E1+E2+U.
- §2 Non-goals — out-of-scope respected (no notebook port, no multi-source-plate, no Echo PLAID tweaks).
- §3 Strategic shape — Phase M moves iDOT into the registry; Phases E1+E2 add Echo + source-layout.
- §4 Dispenser interface — Tasks M3, M4 (iDOT impl), E1.3–E1.6 (Echo impl).
- §5 Iso-behavior migration — Tasks M1, M2 (regression fence), M4–M5 (move + wire).
- §6 Echo CSV format — Tasks E1.2 (helpers), E1.4 (build), E1.5 (write encoding/LF), E1.6 (validate).
- §7 Volume rounding — Tasks E1.7 (function), E1.8 (pipeline wiring).
- §8 Source-plate-import — Task E2.1 (build_liquid_table), E2.2 (pipeline plumbing), E2.3 (golden).
- §9 Config schema — Task U1 (RunConfigModel), M5 (validate_config_dict).
- §10 Backend — Task U2 (/bootstrap), U6 (designer.py forwarding).
- §11 Frontend — Tasks U3 (types), U4 (state), U5 (dropdown), U6 (file picker).
- §12 source_plate_prep — **Gap:** the spec's §12 says `source_plate_prep.py` reads dispense limits from passed plate specs. The plan currently runs Echo with `include_source_prep=False`. **Action:** Add Task E2.4 below.
- §13 Tests — Tasks M2, M6, E1.2–E1.7, E1.9, E1.10, E2.1, E2.3.
- §14 Risks — R1 (Tasks M1, M2 fence), R2 (E1.6, E1.10), R3 (M5 default), R4 (U4), R5 (E1.7), R6 (E2.1), R7 (E1.1), R8 (covered by smoke), R9 (acknowledged).
- §15 Out of scope — respected.
- §16 Acceptance — covered by golden tests + Phase B.
- §17 Phasing — matches plan structure.

Adding Task E2.4 to close the §12 gap:

---

### Task E2.4: Echo source-plate-prep instructions

**Files:**
- Modify: `src/iplaid/source_plate_prep.py`
- Modify: `src/iplaid/pipeline.py`
- Create: `tests/test_source_plate_prep_echo.py`

- [ ] **Step 1: Read `src/iplaid/source_plate_prep.py`** to find where it reads `dispense_min_nL_aq`, `dead_volume_uL_aq_lt`, or other iDOT-spec keys hardcoded by name. Note line numbers.

- [ ] **Step 2: Refactor those reads to use generic spec keys.** The Echo specs file uses `dispense_min_nL`, `dead_volume_uL_dmso`, `effective_reservoir_uL`. Add a small helper at the top of the file:

```python
def _get_spec_value(spec: dict, *keys: str, default=None):
    """Try multiple spec key names (iDOT vs Echo) and return the first present."""
    for k in keys:
        if k in spec:
            return spec[k]
    if default is not None:
        return default
    raise KeyError(f"None of {keys} found in plate spec")
```

Replace iDOT-specific reads, e.g.:
- `spec["dead_volume_uL_aq_lt"]` → `_get_spec_value(spec, "dead_volume_uL_aq_lt", "dead_volume_uL_dmso")`
- `spec["dispense_min_nL_aq"]` → `_get_spec_value(spec, "dispense_min_nL_aq", "dispense_min_nL")`

- [ ] **Step 3: Update `pipeline.py`'s call to `generate_source_plate_prep_instructions`** so the dispenser's loaded `specs` (already in scope) are forwarded. Verify the function signature accepts `source_specs` already; if not, add it.

- [ ] **Step 4: Write a smoke test.**

```python
"""Source-plate-prep tests for both dispensers."""
import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from iplaid.pipeline import run_pipeline_with_inputs


GOLDEN_DIR = Path(__file__).parent / "golden"


def test_source_plate_prep_runs_for_echo(tmp_path: Path) -> None:
    src = GOLDEN_DIR / "echo_basic"
    work = tmp_path / "prep"
    work.mkdir()
    shutil.copy(src / "layout.csv", work / "layout.csv")
    shutil.copy(src / "meta.csv", work / "meta.csv")
    cfg = json.loads((src / "config.json").read_text())
    out_dir = work / "out"
    out_dir.mkdir()
    r = run_pipeline_with_inputs(
        config=cfg,
        layout_path=work / "layout.csv",
        meta_path=work / "meta.csv",
        output_dir=out_dir,
        include_source_prep=True,   # KEY: ensure prep step runs
    )
    assert r["source_prep_instructions"] is not None
    assert len(str(r["source_prep_instructions"])) > 0
```

- [ ] **Step 5: Run.**

```bash
python -m pytest tests/test_source_plate_prep_echo.py -v
```

Expected: pass. If it fails because the prep function reads an iDOT-only key not yet aliased, add the alias in step 2.

- [ ] **Step 6: Run the iDOT goldens to confirm no regression.**

```bash
python -m pytest tests/test_pipeline.py -v
```

Expected: all pass (the iDOT path still resolves the iDOT-spec keys via the `_get_spec_value` aliasing).

- [ ] **Step 7: Commit.**

```bash
git commit -am "feat(source_prep): support Echo plate specs via key aliasing"
```

---

**Placeholder scan:** searched plan for "TBD", "TODO", "fill in", "appropriate", "similar to". None found in step bodies. The phrase "to be filled in" appears once in CLAUDE.md (existing) and is unrelated.

**Type consistency:** confirmed function signatures match across tasks:
- `apply_dispenser_increment(df, increment_nL)` — defined in E1.7, called in E1.8.
- `build_liquid_table(all_rows, protocol_name, *, existing_layout=None)` — defined in E2.1, called in E2.2 and the goldens.
- `EchoDispenser` methods — `build_protocol` (E1.4), `write_protocol` (E1.5), `write_liquids` (E1.6), `validate_export` (E1.6) — match the `Dispenser` Protocol in M3.
- `_pad_source_well`, `_unpad_dest_well`, `_liquid_name_to_sample_name` — defined in E1.2, used in E1.4.
- `SourceLayoutError` — defined in M3 (`base.py`), imported in E2.1.

Plan is internally consistent.

---

## Execution

Plan complete and saved to `docs/superpowers/plans/2026-05-02-echo-dispenser.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration. Best for this plan because Phase M is high-stakes (regression fence) and benefits from focused, isolated context per task.

**2. Inline Execution** — run tasks in this session using the executing-plans skill, with checkpoints for review.

Which approach?
