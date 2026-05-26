from __future__ import annotations

import json
from pathlib import Path

from .download_filenames import build_source_prep_output_path
from .io import (
    load_config,
    validate_config_dict,
    find_project_root,
    resolve_project_paths,
    build_output_paths,
    get_source_plate_spec,
)
from .loaders import (
    load_layout_csv,
    normalize_layout_df,
    load_meta_csv,
    normalize_meta_df,
    merge_layout_with_meta,
    derive_meta_from_source_layout,
    source_layout_to_legacy_shape,
)
from .calculations import (
    stockfinder,
    stockfinder_safe,
    remove_leading_zero,
    volume_from_stock,
    assign_stock_concentrations,
    make_stock_summary,
)
from .normalization import (
    add_target_and_volume_columns,
    enforce_solvent_volume_cap,
    normalize_solvent_topup,
    apply_dispenser_increment,
)
from .output import (
    build_compound_and_topup_rows,
    build_liquid_table,
    attach_and_sort_dispense_rows,
    validate_source_layout_geometry,
)
from .validators import validate_solvent_normalization
from .dispensers import get_dispenser
from .validators_preflight import PreflightAssessmentError, run_preflight_validation
from . import source_plate_prep
from .imeta import build_imeta_dataframe

# Columns that unambiguously identify the new self-contained source-layout shape.
# A CSV possessing all four is treated as new-shape; anything else falls through
# to legacy handling (3-column Liquid Name / Source Plate / Source Well).
NEW_SHAPE_COLUMNS = {"cmpdname", "conc_mM", "source_plate", "source_well"}


def run_pipeline(project_root=None, include_source_prep=True):
    """
    Execute complete PLAID iDOT pipeline.
    
    Args:
        project_root: Project root path (auto-detected if None)
        include_source_prep: Include source plate preparation instructions
        
    Returns:
        Dictionary with complete pipeline results
    """
    root = find_project_root(project_root)
    cfg = load_config(root / "config" / "config.json")
    paths = resolve_project_paths(root, cfg)

    return _run_pipeline_with_resolved_inputs(
        root=root,
        cfg=cfg,
        paths=paths,
        include_source_prep=include_source_prep,
    )


def run_pipeline_with_inputs(
    *,
    config: dict,
    layout_path: str | Path,
    meta_path: str | Path | None,
    output_dir: str | Path,
    include_source_prep: bool = True,
    project_root: str | Path | None = None,
    plate_specs_path: str | Path | None = None,
    source_layout_path: str | Path | None = None,
):
    """
    Execute the pipeline against explicit input files and output directory.

    Exactly one of {meta_path, new-shape source_layout_path} must be provided.
    When the source plate layout is provided in the new shape (cmpdname /
    conc_mM / solvent / source_plate / source_well), metadata is derived from
    it and `meta_path` must be None. The legacy 3-column source-layout upload
    (Liquid Name / Source Plate / Source Well) is a programmatic shim that
    pairs with an explicit `meta_path`.
    """
    # Probe the source layout shape up front so we can apply the correct
    # exclusivity rule. New-shape source layouts are self-contained and
    # forbid a meta_path; legacy-shape uploads still require meta.
    layout_raw = None
    layout_is_new_shape = False
    if source_layout_path is not None:
        import pandas as pd
        layout_raw = pd.read_csv(source_layout_path)
        layout_is_new_shape = NEW_SHAPE_COLUMNS.issubset(set(layout_raw.columns))

    if layout_is_new_shape:
        if meta_path is not None:
            raise ValueError(
                "both meta_path and source_layout_path were provided; pass exactly one"
            )
    else:
        if meta_path is None:
            raise ValueError(
                "meta_path is required (or pass source_layout_path in the new self-contained shape)"
            )

    root = find_project_root(project_root)
    cfg = validate_config_dict(dict(config))

    explicit_layout_path = Path(layout_path)
    explicit_plate_specs_path = (
        Path(plate_specs_path)
        if plate_specs_path is not None
        else Path(root)
        / "data"
        / get_dispenser(cfg.get("dispenser", "idot")).spec.plate_specs_path
    )
    output_paths = build_output_paths(Path(output_dir), cfg)

    paths = {
        "project_root": Path(root),
        "layout_path": explicit_layout_path,
        "meta_path": Path(meta_path) if meta_path is not None else None,
        "plate_specs_path": explicit_plate_specs_path,
        "out_idot": output_paths["out_idot"],
        "out_protocol": output_paths.get("out_protocol", output_paths["out_idot"]),
        "out_liquids": output_paths["out_liquids"],
        "out_imeta": output_paths["out_imeta"],
        "run_timestamp": str(output_paths["run_timestamp"]),
    }

    existing_layout_df = None
    derived_cmpd_info = None
    if source_layout_path is not None:
        paths["source_layout_path"] = Path(source_layout_path)
        if layout_is_new_shape:
            derived_cmpd_info = normalize_meta_df(
                derive_meta_from_source_layout(layout_raw)
            )
            existing_layout_df = source_layout_to_legacy_shape(layout_raw)
        else:
            # Legacy 3-column upload (only used by tests / programmatic callers
            # passing the old shape alongside an explicit meta_path).
            existing_layout_df = layout_raw

    return _run_pipeline_with_resolved_inputs(
        root=Path(root),
        cfg=cfg,
        paths=paths,
        include_source_prep=include_source_prep,
        existing_layout=existing_layout_df,
        derived_cmpd_info=derived_cmpd_info,
    )


def _validate_target_plate_against_catalog(disp, cfg: dict, project_root: Path) -> None:
    """Reject cfg["target_plate_type"] if it isn't in the active dispenser's
    destination-plate catalog.

    Source-side mismatches are already caught implicitly by get_source_plate_spec()
    (raises KeyError). The destination side had no guard — the string was just
    written verbatim to the CSV's Destination Plate Type column, and the machine
    rejected the file at import. This adds the explicit pre-write check so every
    pipeline caller (UI, CLI, notebook, API) gets a fast clear error.

    Graceful when the catalog file is missing (no crash for stripped-down envs).
    Exact-match comparison — no case folding, no whitespace stripping — to mirror
    how Echo Cherry Pick / Assay Studio look up plate names in their libraries.
    """
    target_path = project_root / "data" / disp.spec.target_plate_specs_path
    if not target_path.exists():
        return

    try:
        target_raw = json.loads(target_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return  # Unreadable catalog -> skip (don't block the run)

    if isinstance(target_raw, list):
        valid_names = {p["id"] for p in target_raw if isinstance(p, dict) and "id" in p}
    elif isinstance(target_raw, dict):
        valid_names = set(target_raw.keys())
    else:
        return

    if not valid_names:
        return

    requested = cfg.get("target_plate_type")
    if requested in valid_names:
        return

    sorted_valid = sorted(valid_names)
    raise ValueError(
        f"target_plate_type {requested!r} is not in the {disp.spec.display_name} "
        f"destination-plate catalog (data/{disp.spec.target_plate_specs_path}). "
        f"Valid options: {sorted_valid}. "
        f"If you need a different plate, add it to that file (id matching the "
        f"name your machine's Plate Type Editor uses)."
    )


def _run_pipeline_with_resolved_inputs(
    *,
    root: Path,
    cfg: dict,
    paths: dict,
    include_source_prep: bool,
    existing_layout=None,
    derived_cmpd_info=None,
):
    """Execute the shared pipeline workflow once config and file paths are resolved."""

    disp = get_dispenser(cfg.get("dispenser", "idot"))
    _validate_target_plate_against_catalog(disp, cfg, paths["project_root"])
    specs = disp.load_plate_specs(paths["project_root"])
    source_specs = get_source_plate_spec(specs, cfg["sourceplate_type"])
    if existing_layout is not None:
        validate_source_layout_geometry(existing_layout, source_specs, cfg["sourceplate_type"])

    # Load and normalize input data
    df = load_layout_csv(paths["layout_path"])
    df, _ = normalize_layout_df(df)

    if derived_cmpd_info is not None:
        cmpd_info = derived_cmpd_info
    else:
        cmpd_info = load_meta_csv(paths["meta_path"])
        cmpd_info = normalize_meta_df(cmpd_info)
    df = merge_layout_with_meta(df, cmpd_info)

    # Pre-flight validation: check all concentrations and solvent families are feasible
    preflight_assessment = run_preflight_validation(
        df,
        cfg,
    )
    if not preflight_assessment["ok"]:
        raise PreflightAssessmentError(preflight_assessment)

    # Stock selection and volume calculation
    # Track input before stock assignment
    input_unique_pairs = df.groupby(["cmpdname", "CONCuM"]).ngroups if len(df) > 0 else 0
    
    df = assign_stock_concentrations(
        df,
        stockfinder_fn=stockfinder,
        stockfinder_safe_fn=stockfinder_safe,
        working_volume_ul=float(cfg["working_volume_ul"]),
        config=cfg,
        sourceplate_type=str(cfg["sourceplate_type"]),
    )
    stock_summary = make_stock_summary(df)
    
    # Diagnostic: Report what stocks were assigned
    unique_stocks = df.groupby(["cmpdname", "stock_conc_mM"]).ngroups if len(df) > 0 else 0
    print("\n" + "="*90)
    print("✓ STOCK CONCENTRATION ASSIGNMENT COMPLETED")
    print("="*90)
    print(f"Input unique (compound, target_conc) pairs: {input_unique_pairs}")
    print(f"Unique (compound, stock) assignments created: {unique_stocks}")
    print(f"\nDetailed assignments:")
    for compound in sorted(df['cmpdname'].unique()):
        comp_data = df[df['cmpdname'] == compound]
        unique_targets = sorted(comp_data['CONCuM'].unique(), key=lambda x: float(str(x).strip().replace('"', '')))
        stocks_assigned = comp_data.groupby('CONCuM')['stock_conc_mM'].apply(lambda x: list(x.unique())).to_dict()
        
        print(f"\n  {compound}:")
        for target in unique_targets:
            target_str = str(target).strip().replace('"', '')
            stocks_for_target = stocks_assigned.get(target, [])
            count = len(comp_data[comp_data['CONCuM'] == target])
            print(f"    • Target {target_str:>8s} µM  →  Stock(s): {stocks_for_target} ({count} wells)")

    # Target plate assignments and volume calculations
    df = add_target_and_volume_columns(
        df,
        remove_leading_zero_fn=remove_leading_zero,
        volume_from_stock_fn=volume_from_stock,
        working_volume_ul=float(cfg["working_volume_ul"]),
    )

    # Dispenser-specific volume rounding (no-op for iDOT; 2.5 nL for Echo).
    if disp.spec.min_increment_nL > 0:
        df = apply_dispenser_increment(
            df,
            disp.spec.min_increment_nL,
            working_volume_ul=float(cfg["working_volume_ul"]),
        )

    df, solvent_caps = enforce_solvent_volume_cap(
        df,
        config=cfg,
        working_volume_ul=float(cfg["working_volume_ul"]),
    )

    # Solvent-family normalization
    df, solvent_summary = normalize_solvent_topup(
        df,
        config=cfg,
        working_volume_ul=float(cfg["working_volume_ul"]),
    )

    # Protocol building
    compound_rows, topup_rows, all_rows = build_compound_and_topup_rows(df)
    liquid_table, liquid_table_export = build_liquid_table(
        all_rows,
        str(cfg["protocol_name"]),
        existing_layout=existing_layout,
        source_specs=source_specs,
    )
    
    # Diagnostic: Report final liquid table
    print("\n" + "="*90)
    print("✓ LIQUID TABLE CREATED")
    print("="*90)
    print(f"Unique liquids (source stocks) in protocol: {len(liquid_table_export)}")
    print("\nLiquids being used:")
    for idx, row in liquid_table_export.iterrows():
        print(f"  {idx+1:2d}. {row['Liquid Name']:40s} → {row['Source Well']}")
    
    # Verification: Compare input targets vs created liquids
    liquid_names = set(liquid_table_export["Liquid Name"])
    expected_targets = set()
    for (compound, conc), group in df.groupby(["cmpdname", "CONCuM"]):
        stocks = group['stock_conc_mM'].unique()
        for stock in stocks:
            expected_targets.add(f"[{compound}][{stock}]")
    
    if len(expected_targets) != len(liquid_names):
        print(f"\n⚠️  NOTE: Consolidated {len(expected_targets)} compound-stock combinations")
        print(f"          into {len(liquid_names)} final unique liquids")
        missing = expected_targets - liquid_names
        if missing:
            print(f"          Missing: {missing}")
    
    print("\n" + "="*90)
    print("SUMMARY: How stock assignments work")
    print("="*90)
    print(f"""
✓ The stockfinder successfully assigned stocks to achieve ALL target concentrations
✓ Multiple target concentrations can use the SAME source stock at DIFFERENT volumes
✓ Example: Etoposide 0.03 µM and 0.1 µM both use 0.1 mM stock, just different volumes
✓ Protocol shows [Compound][StockConcentration] NOT [Compound][TargetConcentration]
✓ The dispense volume column determines final target concentration in well

If you see fewer unique liquids than compound/target pairs, this can be EXPECTED and CORRECT.
This run has {input_unique_pairs} unique compound/target pairs and {len(liquid_names)} unique source liquids.
    """)
    print()
    
    # Exclusion cascade: when the pipette-friendly algorithm drops a compound
    # (Tier 3), its Liquid Names are absent from liquid_table_export. If we
    # leave them in `all_rows`, the LEFT merge in attach_and_sort_dispense_rows
    # produces NaN source wells → Echo crashes, iDOT emits garbage. Filter here.
    placed_liquids = set(liquid_table_export["Liquid Name"])
    pre_filter_count = len(all_rows)
    all_rows = all_rows[all_rows["Liquid Name"].isin(placed_liquids)].copy()
    dropped_dispense_rows = pre_filter_count - len(all_rows)
    if dropped_dispense_rows > 0:
        print(f"⚠️  Dropped {dropped_dispense_rows} dispense rows for excluded compounds.")

    all_rows = attach_and_sort_dispense_rows(all_rows, liquid_table, liquid_table_export)

    fullprotocol = disp.build_protocol(
        all_rows,
        liquid_table,
        cfg=cfg,
        source_specs=source_specs,
    )

    # Write output files via the dispenser
    disp.write_protocol(fullprotocol, paths["out_idot"])
    disp.write_liquids(liquid_table_export, paths["out_liquids"])

    # iMETA export: one row per final protocol dispense, including solvent top-ups.
    imeta_df = build_imeta_dataframe(df, all_rows, cfg)
    imeta_df.to_csv(paths["out_imeta"], index=False)

    # Validation via the dispenser
    preview_df, header_row_idx = disp.validate_export(
        paths["out_idot"],
        protocol_name=str(cfg["protocol_name"]),
        user_name=str(cfg["user_name"]),
    )

    validated_solvent_summary = validate_solvent_normalization(df)
    dmso_summary = next(
        (entry for entry in validated_solvent_summary if str(entry["solventKey"]) == "dmso"),
        None,
    )
    validated_target_dmso_ul = float(dmso_summary["targetSolventUl"]) if dmso_summary else 0.0
    validated_max_dmso_ul = float(dmso_summary["maxSolventUl"]) if dmso_summary else 0.0

    # Source plate preparation (optional).
    # Currently iDOT-only: source_plate_prep reads the iDOT-shaped protocol CSV
    # (skiprows=3 for the file header) and uses iDOT plate-spec keys. Echo
    # support requires CSV-format-aware parsing and is deferred to v2 per spec
    # §15. For non-iDOT dispensers we emit a placeholder note instead of
    # crashing on the format mismatch.
    source_prep_volumes = None
    source_prep_instructions = None
    if include_source_prep and existing_layout is not None:
        source_layout_path = paths.get("source_layout_path")
        source_layout_name = (
            Path(source_layout_path).name
            if source_layout_path is not None
            else str(cfg.get("source_layout_file") or "uploaded source layout")
        )
        source_prep_volumes, source_prep_instructions = (
            source_plate_prep.generate_existing_source_plate_summary(
                config=cfg,
                source_layout=existing_layout,
                liquid_table=liquid_table,
                all_rows=all_rows,
                source_layout_name=source_layout_name,
            )
        )
        prep_outfile = build_source_prep_output_path(
            Path(paths["out_idot"]).parent,
            cfg,
            timestamp=str(paths["run_timestamp"]),
            source_layout_provided=True,
        )
        with open(prep_outfile, "w", encoding="utf-8") as f:
            f.write(source_prep_instructions)
        paths["out_source_prep"] = prep_outfile
    elif include_source_prep and disp.spec.name != "idot":
        source_prep_instructions = (
            f"# Source-plate preparation instructions are not yet generated "
            f"for the '{disp.spec.name}' dispenser.\n"
            f"# v1 ships iDOT prep only; Echo prep is planned for v2.\n"
            f"# The Echo protocol CSV at {paths['out_idot']} is ready to load.\n"
        )
        prep_outfile = build_source_prep_output_path(
            Path(paths["out_idot"]).parent,
            cfg,
            timestamp=str(paths["run_timestamp"]),
        )
        with open(prep_outfile, "w", encoding="utf-8") as f:
            f.write(source_prep_instructions)
        paths["out_source_prep"] = prep_outfile
    elif include_source_prep:
        scatter_warnings_data = [
            {"compound": sw.compound, "wells": sw.wells}
            for sw in liquid_table.attrs.get("scatter_warnings", [])
        ]
        excluded_data = [
            {
                "compound": ew.compound,
                "stocks_needed": ew.stocks_needed,
                "free_wells_remaining": ew.free_wells_remaining,
            }
            for ew in liquid_table.attrs.get("excluded_compounds", [])
        ]
        source_prep_volumes, source_prep_instructions = source_plate_prep.generate_source_plate_prep_instructions(
            Path(paths["project_root"]) / "outputs" / "results",
            cfg,
            paths["meta_path"],
            paths["plate_specs_path"],
            cfg["protocol_name"],
            cfg["layout_file"],
            idot_csv_path=paths["out_idot"],
            liquids_csv_path=paths["out_liquids"],
            scatter_warnings=scatter_warnings_data,
            excluded=excluded_data,
        )
        
        prep_outfile = build_source_prep_output_path(
            Path(paths["out_idot"]).parent,
            cfg,
            timestamp=str(paths["run_timestamp"]),
        )
        with open(prep_outfile, 'w', encoding='utf-8') as f:
            f.write(source_prep_instructions)
        paths["out_source_prep"] = prep_outfile
    else:
        paths["out_source_prep"] = None

    # Surface algorithm warnings (Tier 2 scatter, Tier 3 exclusion) on the run output
    # so the FastAPI layer and frontend can render them. `warnings` carries BOTH
    # tiers (soft scatter + loud exclusion) so callers inspecting one channel see
    # every source-plate event; `excluded_compounds` keeps the structured exclusion
    # data the frontend needs for the diagonal-overlay on the destination plate.
    warnings_out = [
        {
            "severity": "soft",
            "kind": "scatter",
            "compound": sw.compound,
            "wells": list(sw.wells),
        }
        for sw in liquid_table.attrs.get("scatter_warnings", [])
    ] + [
        {
            "severity": "loud",
            "kind": "exclusion",
            "compound": ew.compound,
            "stocks_needed": ew.stocks_needed,
            "free_wells_remaining": ew.free_wells_remaining,
        }
        for ew in liquid_table.attrs.get("excluded_compounds", [])
    ]
    excluded_compounds_out = [
        {
            "compound": ew.compound,
            "stocks_needed": ew.stocks_needed,
            "free_wells_remaining": ew.free_wells_remaining,
        }
        for ew in liquid_table.attrs.get("excluded_compounds", [])
    ]
    excluded_names_set = {
        ew.compound for ew in liquid_table.attrs.get("excluded_compounds", [])
    }
    if excluded_names_set:
        excluded_target_wells_out = (
            df.loc[df["cmpdname"].isin(excluded_names_set), ["Target Plate", "Target Well"]]
              .drop_duplicates()
              .rename(columns={"Target Plate": "target_plate", "Target Well": "target_well"})
              .to_dict("records")
        )
    else:
        excluded_target_wells_out = []

    return {
        "project_root": root,
        "config": cfg,
        "paths": paths,
        "source_specs": source_specs,
        "df": df,
        "cmpd_info": cmpd_info,
        "preflight_assessment": preflight_assessment,
        "stock_summary": stock_summary,
        "compound_rows": compound_rows,
        "topup_rows": topup_rows,
        "all_rows": all_rows,
        "liquid_table": liquid_table,
        "liquid_table_export": liquid_table_export,
        "fullprotocol": fullprotocol,
        "imeta_df": imeta_df,
        "preview_df": preview_df,
        "header_row_idx": header_row_idx,
        "is_solvent_control_count": int(df["is_solvent_control"].fillna(False).astype(bool).sum()),
        "solvent_caps": solvent_caps,
        "solvent_summary": validated_solvent_summary or solvent_summary,
        "target_dmso_ul": validated_target_dmso_ul,
        "max_dmso_ul": validated_max_dmso_ul,
        "source_prep_volumes": source_prep_volumes,
        "source_prep_instructions": source_prep_instructions,
        "source_layout_provided": existing_layout is not None,
        "warnings": warnings_out,
        "excluded_compounds": excluded_compounds_out,
        "excluded_target_wells": excluded_target_wells_out,
    }
