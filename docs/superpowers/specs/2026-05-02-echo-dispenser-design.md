---
type: design-spec
status: draft
project: iPLAID (target) / Echo (origin)
date: 2026-05-02
tags: [design, spec, iplaid, echo, dispenser]
---

# Echo dispenser support in iPLAID — Design Spec

> **Origin**: this spec was drafted in the Echo repo (where the legacy `colo8-input` reference lives) and migrated here for implementation. The legacy reference remains at `../../../../Echo/legacy_colo8-input/` (separate repo).
>
> **Companion plan**: [`../plans/2026-05-02-echo-dispenser.md`](../plans/2026-05-02-echo-dispenser.md)

## 1. Goal

Add Echo acoustic liquid handler as a selectable dispenser in iPLAID, alongside the existing iDOT backend, so the same iPLAID design pipeline can produce a protocol file consumed by either machine. The user picks the dispenser via a UI dropdown; the backend dispatches to the correct writer/validator under the hood. iDOT behavior must remain bit-for-bit unchanged.

## 2. Non-goals

- Porting the legacy `colo8-input` notebook or its source-plate generator. Legacy is reference-only; its math is already represented (more generally) by iPLAID's calc engine.
- Multiple Echo source plates per run. v1 is single-source-plate.
- Echo-specific PLAID solver tweaks. The PLAID layout input is the same shape as today.
- Backwards-compat shims for downstream consumers. iPLAID outputs (iDOT CSV, liquids CSV, iMETA CSV, source-prep instructions) keep their current schemas for the iDOT path. The new Echo CSV schema is additive.

## 3. Strategic shape

iPLAID's `_run_pipeline_with_resolved_inputs` already separates dispenser-agnostic work (load, preflight, stockfinder, volume calc, solvent cap, solvent topup, build dispense rows, build liquid table, attach + sort) from dispenser-specific work (build the vendor protocol, write to file, validate the file). The intermediate `all_rows` DataFrame — `Target Plate, Target Well, Liquid Name, Volume [uL], Source Plate, Source Well, compound, stock_mM, is_control_liquid` — is the canonical dispense table. Echo support is a second writer over the same data.

Approach A (chosen): introduce a `dispensers/` strategy subpackage that owns dispenser-specific behavior behind a small interface. iDOT becomes one implementation, Echo a second. The pipeline imports the registry, looks up the dispenser by config name, and calls the interface methods.

```
src/iplaid/
  __init__.py                          (existing — exports unchanged)
  pipeline.py                          (modified — uses dispenser registry)
  loaders.py                           (unchanged)
  calculations.py                      (unchanged)
  normalization.py                     (extended — adds increment-rounding step, off by default)
  validators_preflight.py              (unchanged)
  imeta.py                             (unchanged)
  source_plate_prep.py                 (extended — reads min-volume from dispenser specs instead of hardcoding)
  io.py                                (extended — loads per-dispenser plate-specs file)
  output.py                            (shrunk — shared dispense-table builders only; iDOT functions re-exported from dispensers/idot.py for import-path stability)
  dispensers/
    __init__.py                        (NEW — get_dispenser(name) registry)
    base.py                            (NEW — Dispenser ABC + DispenserSpec dataclass)
    idot.py                            (NEW — iDOT impl, moved verbatim from output.py and validators.py)
    echo.py                            (NEW — Echo impl)
  validators.py                        (shrunk — dispenser-agnostic validators only; iDOT-specific moved to dispensers/idot.py and re-exported for import-path stability)
data/
  source_plate_specs.json              (existing — iDOT plates)
  echo_plate_specs.json                (NEW — Echo plates)
backend/app/
  models.py                            (extended — adds dispenser field)
  main.py / bootstrap                  (extended — exposes per-dispenser plate types)
frontend/src/
  types.ts                             (extended — RunConfig.dispenser)
  components/workbench/RunConfigPanel.tsx  (extended — dispenser dropdown + dependent plate dropdown + optional source-layout upload)
  workbenchState.tsx                   (extended — dispenser default + plate-list refresh on dispenser change)
tests/
  test_pipeline.py                     (extended — new echo path)
  golden/                              (existing iDOT goldens unchanged)
  golden/echo/                         (NEW — Echo CSV byte-equal fixtures)
  test_dispensers.py                   (NEW — interface conformance for each dispenser)
  test_echo_output.py                  (NEW — Echo writer unit tests)
  test_source_plate_import.py          (NEW — existing-layout pathway)
```

## 4. The Dispenser interface

`src/iplaid/dispensers/base.py` defines a small interface that each backend implements. Keeping the surface narrow is the whole point — anything that's the same for both backends stays in shared modules.

```python
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import pandas as pd


@dataclass(frozen=True)
class DispenserSpec:
    """Static metadata about a dispenser. Loaded from the registry."""
    name: str                              # "idot" | "echo"
    display_name: str                      # "iDOT" | "Echo"
    plate_specs_path: str                  # path under data/, e.g. "source_plate_specs.json"
    min_increment_nL: float                # 0 for iDOT (no rounding), 2.5 for Echo
    default_sourceplate_type: str          # "S.100 Plate" | "384PP_DMSO2"
    default_target_plate_type: str         # "MWP 384" | "Corning_384w_3784"


class Dispenser(Protocol):
    spec: DispenserSpec

    def load_plate_specs(self, project_root: Path) -> dict:
        """Load the dispenser's plate-spec catalog."""
        ...

    def build_protocol(
        self,
        all_rows: pd.DataFrame,
        liquid_table: pd.DataFrame,
        *,
        cfg: dict,
        source_specs: dict,
    ) -> pd.DataFrame:
        """Produce the vendor-formatted protocol DataFrame ready to write."""
        ...

    def write_protocol(self, protocol_df: pd.DataFrame, out_path: Path) -> None:
        """Write protocol to disk using vendor-required encoding/line endings."""
        ...

    def write_liquids(self, liquid_table_export: pd.DataFrame, out_path: Path) -> None:
        """Write the liquid mapping file. May be a no-op for dispensers that don't need one."""
        ...

    def validate_export(
        self,
        out_path: Path,
        *,
        protocol_name: str,
        user_name: str,
    ) -> tuple[pd.DataFrame, int]:
        """Read back the written file and verify vendor-format invariants. Returns (preview_df, header_row_idx)."""
        ...
```

Registry in `dispensers/__init__.py`:

```python
from .idot import IDotDispenser
from .echo import EchoDispenser

_REGISTRY = {
    "idot": IDotDispenser(),
    "echo": EchoDispenser(),
}

def get_dispenser(name: str) -> Dispenser:
    if name not in _REGISTRY:
        raise ValueError(f"Unknown dispenser '{name}'. Known: {list(_REGISTRY)}")
    return _REGISTRY[name]

def list_dispensers() -> list[DispenserSpec]:
    return [d.spec for d in _REGISTRY.values()]
```

Pipeline integration is local — `_run_pipeline_with_resolved_inputs` becomes:

```python
disp = get_dispenser(cfg.get("dispenser", "idot"))
specs = disp.load_plate_specs(paths["project_root"])
source_specs = get_source_plate_spec(specs, cfg["sourceplate_type"])
# ... (existing dispenser-agnostic steps, unchanged) ...

# NEW: dispenser-aware volume rounding (no-op for iDOT)
if disp.spec.min_increment_nL > 0:
    df = apply_dispenser_increment(df, disp.spec.min_increment_nL)

# ... (existing build_compound_and_topup_rows / build_liquid_table / attach_and_sort) ...

protocol = disp.build_protocol(all_rows, liquid_table, cfg=cfg, source_specs=source_specs)
disp.write_protocol(protocol, paths["out_protocol"])
disp.write_liquids(liquid_table_export, paths["out_liquids"])
preview_df, header_row_idx = disp.validate_export(
    paths["out_protocol"], protocol_name=cfg["protocol_name"], user_name=cfg["user_name"]
)
```

The only behavioral changes versus today are: (a) `paths["out_idot"]` is renamed to `paths["out_protocol"]` (file extension still `.csv`; iDOT path still produces an identical file), and (b) the new `apply_dispenser_increment` step which is a no-op for iDOT.

## 5. Iso-behavior migration of iDOT

This is the part the user flagged as risky. The plan:

**Phase M (migration)** — happens BEFORE any Echo code is written. Purely a refactor.

1. Add iDOT golden tests if not already covering byte-equality of `<protocol>.csv`, `<liquids>.csv`, `<imeta>.csv`, and `<source_prep>.txt`. Verify they pass on `main`. This is the regression fence.
2. Create `src/iplaid/dispensers/{__init__.py, base.py, idot.py}`.
3. Move `format_protocol_volume_ul`, `build_full_protocol`, `write_protocol_file`, `write_liquids_file`, `write_outputs` from `output.py` into `IDotDispenser` methods (or module-level functions imported by it). Re-export from `output.py` with deprecation comments to ease the transition (delete on next pass; out of scope for v1).
4. Move `validate_export_file` from `validators.py` into `IDotDispenser.validate_export`. Same re-export trick.
5. Update `pipeline.py` to call `disp = get_dispenser("idot")` and use the methods.
6. Run all tests. Goldens must pass byte-equal. **No commit if any test fails.**
7. Run iPLAID locally end-to-end once with a known input. Confirm the produced files are byte-equal to a pre-migration run (manual diff, kept as a one-time verification artifact).

After Phase M, every iDOT behavior is preserved and we have a registry with one entry. Phase E (Echo) then adds the second.

## 6. Echo dispenser implementation

`src/iplaid/dispensers/echo.py` produces the Echo CSV. The format is **vendor-imposed** — exact column case/spelling, asymmetric well padding, decimal volume in nL. Below is the truth table extracted from the legacy `print_echo_colo8-v3-VP-organoid-48h-P1-L1.csv`.

### 6.1 Echo CSV format — must-not-break truth table

| # | Header (exact) | Source | Format | Example |
|---|---|---|---|---|
| 1 | `Sample Name` | `[compound][stock_mM]` joined as `compound[stock_mM]` (no brackets, single dot stock) | string | `gemcitabine[1.0]` |
| 2 | `Source Plate Name` | from `liquid_table["Source Plate"]` | string | `source_dmso` |
| 3 | `Source well` | source well **zero-padded** | `[A-Z][0-9]{2}` | `A07` |
| 4 | `Destination Plate Barcode` | from `all_rows["Target Plate"]` | string | `colo8-v3-VP-organoid-48h-P1-L1` |
| 5 | `destination well` (lowercase 'd') | destination well **NOT zero-padded** | `[A-Z][0-9]+` | `B2` |
| 6 | `Transfer Volume` | volume in **nL**, multiple of 2.5 | `%.1f` | `12.5` |
| 7 | `Source Plate Type` | vendor SKU from plate specs | string | `384PP_DMSO2` |
| 8 | `Destination Plate Type` | vendor SKU from cfg/plate specs | string | `Corning_384w_3784` |
| 9 | `Destination Well X Offset` | from plate specs | int | `1050` |
| 10 | `Destination Well Y Offset` | from plate specs | int | `-1050` |

**Encoding**: UTF-8, no BOM, line ending `\n` (LF). (iDOT uses CRLF + BOM via `utf-8-sig` — Echo does NOT.) Confirmed against the legacy file; the Echo writer must explicitly set `lineterminator="\n"` and `encoding="utf-8"`.

**Sample Name format note**: liquid_table emits `Liquid Name` as `[compound][stock_mM]` (with brackets), e.g. `[gemcitabine][1.0]`. Echo wants the brackets-around-compound form `gemcitabine[1.0]`. The Echo writer strips the leading bracket and replaces `][` with `[` — see `_liquid_name_to_sample_name` helper.

### 6.2 Well padding helpers

```python
def pad_source_well(well: str) -> str:
    """A1 -> A01, B12 -> B12. Always 2-digit number."""
    m = re.match(r"^([A-Z])(\d+)$", well)
    if not m:
        raise ValueError(f"Bad well: {well!r}")
    return f"{m.group(1)}{int(m.group(2)):02d}"

def unpad_dest_well(well: str) -> str:
    """A01 -> A1, B12 -> B12. Strips leading zeros."""
    m = re.match(r"^([A-Z])(\d+)$", well)
    if not m:
        raise ValueError(f"Bad well: {well!r}")
    return f"{m.group(1)}{int(m.group(2))}"
```

Both helpers live in `dispensers/echo.py` (private, not exported). They're tiny and Echo-specific.

### 6.3 EchoDispenser methods

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

    def load_plate_specs(self, project_root):
        with open(Path(project_root) / "data" / self.spec.plate_specs_path) as f:
            return json.load(f)

    def build_protocol(self, all_rows, liquid_table, *, cfg, source_specs):
        # 1. Join all_rows with liquid_table on Liquid Name (already done by attach_and_sort_dispense_rows)
        # 2. Compose the 10 columns:
        out = pd.DataFrame()
        out["Sample Name"] = all_rows["Liquid Name"].map(_liquid_name_to_sample_name)
        out["Source Plate Name"] = all_rows["Source Plate"]
        out["Source well"] = all_rows["Source Well"].map(pad_source_well)
        out["Destination Plate Barcode"] = all_rows["Target Plate"]
        out["destination well"] = all_rows["Target Well"].map(unpad_dest_well)
        out["Transfer Volume"] = (all_rows["Volume [uL]"] * 1000.0).map(lambda v: f"{v:.1f}")
        out["Source Plate Type"] = cfg["sourceplate_type"]
        out["Destination Plate Type"] = cfg["target_plate_type"]
        out["Destination Well X Offset"] = source_specs["x_offset"]
        out["Destination Well Y Offset"] = source_specs["y_offset"]
        return out

    def write_protocol(self, protocol_df, out_path):
        protocol_df.to_csv(out_path, index=False, encoding="utf-8", lineterminator="\n")

    def write_liquids(self, liquid_table_export, out_path):
        # Echo's protocol is self-contained (Sample Name + Source Plate + Source well are inline).
        # We still emit the same liquid table for iMETA traceability and lab QC.
        liquid_table_export.to_csv(out_path, index=False)

    def validate_export(self, out_path, *, protocol_name, user_name):
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
        bad_vol = df[(df["Transfer Volume"].astype(float) % 2.5).round(6) != 0]
        if len(bad_vol) > 0:
            raise ValueError(f"{len(bad_vol)} rows have non-2.5 nL volumes")
        if df["Source well"].str.match(r"^[A-Z]\d{2}$").eq(False).any():
            raise ValueError("Source wells must be 2-digit zero-padded")
        if df["destination well"].str.match(r"^[A-Z]\d+$").eq(False).any():
            raise ValueError("Destination wells malformed")
        if df.isna().any().any():
            raise ValueError("Echo CSV contains NaN")
        return df.head(20), 0  # preview, header_row_idx
```

### 6.4 Echo plate specs file

`data/echo_plate_specs.json`:

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
    "notes": "Echo 384-well low dead volume DMSO source plate. X/Y offsets are vendor defaults."
  }
}
```

Schema rules:
- `dispense_min_nL` ≥ 2.5 (Echo's hardware limit).
- `dispense_max_nL_dmso` is the per-transfer cap; the writer rejects any row above it during `validate_export`.
- `x_offset` / `y_offset` are vendor-tuned constants per plate combo. Hardcoded in legacy as 1050/-1050 — moved here so a plate swap is data-only.

A second entry covering aqueous source plates can be added later (out of scope for v1, but the schema accommodates it without change).

## 7. Volume rounding (Echo's 2.5 nL constraint)

New function in `normalization.py`:

```python
def apply_dispenser_increment(df: pd.DataFrame, increment_nL: float) -> pd.DataFrame:
    """
    Round each compound's transfer volume to the nearest dispenser increment, then
    back-calculate the achieved CONCuM so downstream metadata (iMETA, reports)
    reflect what was actually dispensed, not what was requested.

    No-op when increment_nL == 0. iDOT path never invokes this.
    """
    if increment_nL <= 0:
        return df

    df = df.copy()
    vol_nL = df["Volume [uL]"] * 1000.0
    rounded_nL = (vol_nL / increment_nL).round() * increment_nL
    df["Volume_nL_unrounded"] = vol_nL
    df["Volume [uL]"] = rounded_nL / 1000.0

    # Back-calculate achieved CONCuM where stock_conc_mM is set
    has_stock = df["stock_conc_mM"].fillna(0) > 0
    df.loc[has_stock, "CONCuM_requested"] = df.loc[has_stock, "CONCuM"]
    df.loc[has_stock, "CONCuM"] = (
        df.loc[has_stock, "Volume [uL]"] * df.loc[has_stock, "stock_conc_mM"]
        * 1000.0 / df.loc[has_stock, "well_vol_uL"]
    )

    # Warn (do NOT raise) if any well's deviation exceeds 5%. Biologists may accept it; iPLAID
    # already lets the user run with diagnostics rather than refusing borderline configurations.
    deviation_pct = ((df["CONCuM"] - df["CONCuM_requested"]).abs()
                     / df["CONCuM_requested"].replace(0, pd.NA) * 100)
    over = df[deviation_pct > 5.0]
    if len(over) > 0:
        print(f"⚠ {len(over)} wells have >5% concentration deviation after rounding to "
              f"{increment_nL} nL increments. Review CONCuM vs CONCuM_requested in the iMETA export.")

    return df
```

Called from `_run_pipeline_with_resolved_inputs` after `add_target_and_volume_columns` and before `enforce_solvent_volume_cap`. Pre-existing iDOT tests do not invoke it (`min_increment_nL=0`).

## 8. Source-plate-import generalization

Today [src/iplaid/output.py:106-112](../../../src/iplaid/output.py#L106-L112) auto-assigns wells `A1, A2, ..., H12` to liquids in sort order. We extend `build_liquid_table` to optionally consume a user-supplied layout DataFrame.

### 8.1 Existing-layout CSV schema

Two columns minimum: `Source Well`, `Liquid Name`. Optional column `Source Plate` (defaults to `SRC_<protocol_name>`).

```
Source Well,Liquid Name
A07,[gemcitabine][1.0]
A10,[etoposide][10.0]
A12,[dmso][0.0]
...
```

The user can produce this file from a pre-prepared physical source plate. Same shape works for both iDOT and Echo.

### 8.2 Function signature change

```python
def build_liquid_table(
    all_rows: pd.DataFrame,
    protocol_name: str,
    *,
    existing_layout: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    If existing_layout is None: auto-assign wells A1..H12 in sort order (current behavior).
    If existing_layout is provided: use those wells; raise SourceLayoutError if any
    required Liquid Name is missing or any layout entry is unused.
    """
```

### 8.3 Validation rules for `existing_layout`

- Every Liquid Name in `all_rows` must appear in `existing_layout`. Missing → `SourceLayoutError("Layout missing required liquids: …")`.
- No duplicate `Source Well` entries in `existing_layout`. Duplicate → `SourceLayoutError`.
- Wells must match `[A-Z]\d+` and fit the source plate's row/col bounds (looked up from plate specs).
- Unused layout entries: warn (not fail) — user might intentionally include extras.
- Source Plate column may be missing — defaults to `SRC_<protocol_name>` (matches current auto-assign behavior).

### 8.4 Pipeline plumbing

`run_pipeline_with_inputs` gets a new optional kwarg `source_layout_path: str | Path | None = None`. If provided, `pd.read_csv` it once at the start and pass the DataFrame into `build_liquid_table`. The web app `/run` endpoint passes the upload through; a CLI run can pass a file path. Default `None` preserves current behavior 100%.

## 9. Config schema additions

`config.template.json` gains one field:

```json
{
  "dispenser": "idot",
  ...existing fields...
}
```

Default `"idot"` so any pre-existing config that lacks the field continues to behave as it does today.

`backend/app/models.py` `RunConfigModel` gains:

```python
dispenser: Literal["idot", "echo"] = Field(default="idot")
```

`io.py` `validate_config_dict` gains a check that `cfg["dispenser"]` is one of the registered names; default `"idot"` if absent.

## 10. Backend (`backend/app/`) changes

- `models.py`: add `dispenser` field as above.
- `main.py` (or wherever the bootstrap endpoint lives): the `/bootstrap` (or equivalent) response gains a `dispensers` array with `{name, display_name, default_sourceplate_type}` and a `plate_types_by_dispenser` map keyed by dispenser name. Existing `sourcePlateTypes` field stays for backwards compat but becomes the iDOT entry of the new map.
- `designer.py` / `design_worker.py`: pass `cfg["dispenser"]` through to `run_pipeline_with_inputs` (already happens since `cfg` is forwarded as a dict, but verify).
- `jobs.py`: status JSON gains the dispenser field automatically when persisted via `model_dump()`.
- Existing job records (no `dispenser` field): default to `"idot"` on read to avoid breaking historical job replays.

## 11. Frontend (`frontend/src/`) changes

`types.ts`:

```ts
export interface RunConfig {
  ...
  dispenser: "idot" | "echo";
  source_layout_file?: string | null;   // optional uploaded filename
  ...
}

export interface BootstrapResponse {
  ...
  dispensers: { name: string; display_name: string; default_sourceplate_type: string }[];
  plate_types_by_dispenser: { [dispenser: string]: string[] };
}
```

`workbenchState.tsx`: when `dispenser` changes, (a) reset `sourceplate_type` to the dispenser's default so a stale "S.100 Plate" doesn't get sent with `dispenser: "echo"`, and (b) clear `source_layout_file` since a layout produced for an Echo plate isn't usable on an iDOT plate (different well counts, different liquid sets).

`RunConfigPanel.tsx`: directly above the existing "Source plate" dropdown, add:

```jsx
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

The "Source plate" dropdown's options become `bootstrap.plate_types_by_dispenser[config.dispenser]` instead of the flat `bootstrap.sourcePlateTypes`. (Add a fallback so an old `sourcePlateTypes` field still works.)

Optional source-layout file picker (collapsible "Advanced" section, off by default — keeps the v1 surface minimal):

```jsx
<label>
  <span>Source plate layout (optional)</span>
  <input type="file" accept=".csv" onChange={handleSourceLayoutUpload} />
</label>
```

When set, the upload posts to a new endpoint `/upload/source-layout` (or piggybacks the existing layout upload mechanism) and the resulting filename gets stuffed into `config.source_layout_file`.

`ResultsPage.tsx` line 181 (the spec lookup) currently reads from a single `sourcePlateTypes` source — it gets the dispenser-keyed lookup as well. Trivially mechanical change.

## 12. Source-plate-prep instructions for Echo

`source_plate_prep.py` today reads `min_pipette_volume_uL` from cfg and assumes iDOT plate semantics. The function gets a small extension: it reads dispense limits from the dispenser's plate specs (already loaded in pipeline) instead of cfg-only constants. For Echo, the prep instructions become "load X µL into source well Y of plate type 384PP_DMSO2"; the math is the same (compound consumption × overage + dead volume).

Concretely: pass `dispenser` and `source_specs` to `generate_source_plate_prep_instructions(...)` and let it read `dead_volume_uL` and `effective_reservoir_uL` from `source_specs` (both files have these keys; the iDOT path keeps reading them as it does today).

## 13. Testing strategy

### 13.1 iDOT regression fence (Phase M)

- New test `tests/test_dispensers.py::test_idot_registry_returns_dispenser` — registry hands back an `IDotDispenser`.
- Existing `tests/test_pipeline.py::test_run_pipeline_*` continue to call `run_pipeline_with_inputs` with no `dispenser` field → defaults to `"idot"` → produce byte-identical files. Goldens unchanged.
- New test `tests/test_pipeline.py::test_idot_explicit_dispenser` — passes `cfg["dispenser"]="idot"` explicitly, asserts byte-equal to the implicit-default golden.
- Manual smoke run pre/post Phase M — diff the four outputs (protocol, liquids, imeta, source-prep) using `diff -q`. Must be empty.

### 13.2 Echo correctness (Phase E)

- `tests/test_echo_output.py`:
  - `test_pad_source_well` / `test_unpad_dest_well` — boundary cases (A1, A01, A12, H24).
  - `test_liquid_name_to_sample_name` — `[gemcitabine][1.0]` → `gemcitabine[1.0]`.
  - `test_build_protocol_columns` — given a synthetic 5-row `all_rows` + `liquid_table`, assert column order and content.
  - `test_volume_format` — assert `Transfer Volume` always renders as `%.1f` and is a multiple of 2.5.
  - `test_validate_export_rejects_non_increment` — corrupted CSV with 12.7 nL fails validation.

- `tests/golden/echo/<fixture>/` — for each fixture:
  - Inputs: a PLAID layout CSV + meta CSV + config JSON with `dispenser: "echo"`.
  - Expected outputs: `print_echo_<protocol>.csv` byte-equal.
  - Suggested first fixture: a re-run of the legacy `colo8-v3-VP-organoid-48h-P1-L1.csv` PLAID input through iPLAID, with the resulting Echo CSV captured as the golden. (Not the legacy output verbatim — iPLAID may pick stocks differently, and that's fine; we lock our own bit-for-bit reference.)

- `tests/test_pipeline.py::test_run_pipeline_echo_smoke` — full run, asserts file exists, has 10 columns with exact headers, ≥1 row.

### 13.3 Source-plate-import (Phase E)

- `tests/test_source_plate_import.py`:
  - `test_layout_validates_required_liquids` — missing liquid raises `SourceLayoutError`.
  - `test_layout_rejects_duplicate_wells`.
  - `test_layout_used_when_provided` — assigned wells match the supplied layout, not auto-assignment.
  - `test_layout_none_preserves_auto_assign` — default behavior identical.
  - Each runs against both `idot` and `echo` dispensers (parametrized).

### 13.4 Interface conformance

- `tests/test_dispensers.py::test_each_dispenser_implements_interface` — for every entry in the registry, assert `spec` exists, all interface methods are callable, and a synthetic round-trip (build → write → read → validate) produces a non-empty preview.

## 14. Risk register

| # | Risk | Mitigation |
|---|---|---|
| R1 | Phase M migration silently breaks iDOT goldens | Run goldens locally before AND after each commit in Phase M. Tag the pre-migration commit; abort and revert if goldens diverge. |
| R2 | Echo CSV format wrong (vendor rejects file) | Golden-file regression against a known-good legacy CSV. Validator on every write. Manual bench test with one real run before declaring v1 complete. |
| R3 | `dispenser` field absent in old configs/jobs | Default to `"idot"` in `validate_config_dict`, `RunConfigModel`, frontend `workbenchState`. Verify with a unit test that loads a pre-migration config JSON. |
| R4 | UI sends Echo source plate to iDOT pipeline (or vice versa) due to dispenser/plate-type drift | `workbenchState` resets `sourceplate_type` to the dispenser's default on dispenser change. Backend rejects mismatched (dispenser, sourceplate_type) pairs in `validate_config_dict`. |
| R5 | Volume rounding back-calc produces NaN where stock is 0 (solvent control rows) | `apply_dispenser_increment` only back-calcs where `stock_conc_mM > 0`. Solvent topup rows pass through with rounded volume but no CONCuM rewrite. Covered by unit test. |
| R6 | Source-layout upload missing a liquid the pipeline auto-derives later (e.g. solvent control) | Validation runs after `build_compound_and_topup_rows` so it sees the full liquid set including topups. Error message lists missing names. |
| R7 | Echo X/Y offsets vary by plate combo and are wrong for a setup we haven't seen | Per-plate spec entries in `echo_plate_specs.json`. If a lab adds a new plate, they add a JSON entry; no code change. |
| R8 | iMETA expects iDOT-shaped fields | `imeta.py` reads from `df` and `all_rows` which are dispenser-agnostic. Verified by reading the function. Add an iMETA-shape test in the Echo path to be explicit. |
| R9 | Golden test for Echo locks in a specific stockfinder choice that future stockfinder changes would break | Same risk applies to existing iDOT goldens — manageable. If stockfinder changes intentionally, regenerate goldens deliberately. |

## 15. Out of scope / explicit deferrals

- **Multi-source-plate Echo runs.** v1 assumes a single Echo source plate. The dispenser interface accommodates multiple plates if `liquid_table["Source Plate"]` ever has > 1 unique value, but v1 doesn't ship UI or tests for that.
- **Aqueous Echo plate types.** Spec schema allows them; v1 adds only `384PP_DMSO2`.
- **Echo source-plate-prep PDF/HTML report.** v1 reuses `source_plate_prep.py` text instructions; no Echo-specific report. Defer to v2.
- **Removing the legacy Echo repo.** Once the Echo backend is shipped in iPLAID and the golden test stands in, the standalone Echo repo (this one) can be archived. That's a follow-up cleanup, not part of this work.
- **Dropping iDOT.** Never. Both backends coexist permanently.

## 16. Acceptance criteria

The work is done when:

1. All existing iPLAID tests pass byte-equal on the iDOT path with no source code changes to the goldens.
2. A new Echo run with `dispenser: "echo"`, a colo8-style PLAID input, and the legacy-style compound library produces an Echo CSV that:
   - Has exactly 10 columns with the exact headers in §6.1.
   - Every `Transfer Volume` is a multiple of 2.5 nL formatted as `%.1f`.
   - Source wells zero-padded; destination wells unpadded.
   - Validates clean against the Echo-side validator.
3. A run with `dispenser: "echo"` AND `source_layout_path` provided maps source wells from the supplied layout, fails loudly on missing liquids, and produces a byte-equal Echo CSV matching the golden for that fixture.
4. The UI lets the user pick `iDOT` / `Echo`, refreshes the plate dropdown accordingly, and accepts an optional source-layout upload.
5. End-to-end: a colleague who currently runs the legacy notebook can upload the same PLAID layout to iPLAID, pick `Echo`, and get an Echo CSV their machine accepts.

## 17. Implementation phasing

- **Phase M — iDOT migration** (refactor only, no new behavior). Acceptance: goldens pass.
- **Phase E1 — Echo writer** (`dispensers/echo.py`, plate specs JSON, `apply_dispenser_increment`, golden). Acceptance: Echo smoke test + golden-file test pass.
- **Phase E2 — Source-plate-import** (extend `build_liquid_table`, validation, pipeline plumbing). Acceptance: parametrized tests pass for both dispensers.
- **Phase U — UI** (dispenser dropdown, plate-list refresh, optional source-layout upload). Acceptance: manual UI run succeeds for both dispensers.
- **Phase B — Bench validation** (one real Echo run by a colleague; one real iDOT run regression). Acceptance: protocols accepted by the respective machines.

The implementation plan (separate document, produced by `writing-plans`) breaks each phase into TDD-ordered steps with file-by-file edits and test commands.
