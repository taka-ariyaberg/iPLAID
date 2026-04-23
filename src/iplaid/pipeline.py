from __future__ import annotations

from pathlib import Path

from src.iplaid.download_filenames import build_source_prep_output_path
from src.iplaid.io import (
    load_config,
    validate_config_dict,
    find_project_root,
    resolve_project_paths,
    build_output_paths,
    load_source_plate_specs,
    get_source_plate_spec,
)
from src.iplaid.loaders import (
    load_layout_csv,
    normalize_layout_df,
    load_meta_csv,
    normalize_meta_df,
    merge_layout_with_meta,
)
from src.iplaid.calculations import (
    stockfinder,
    stockfinder_safe,
    remove_leading_zero,
    volume_from_stock,
    assign_stock_concentrations,
    make_stock_summary,
)
from src.iplaid.normalization import (
    add_target_and_volume_columns,
    enforce_solvent_volume_cap,
    normalize_solvent_topup,
)
from src.iplaid.output import (
    build_compound_and_topup_rows,
    build_liquid_table,
    attach_and_sort_dispense_rows,
    build_full_protocol,
    write_outputs,
)
from src.iplaid.validators import validate_export_file, validate_solvent_normalization
from src.iplaid.validators_preflight import PreflightAssessmentError, run_preflight_validation
from src.iplaid import source_plate_prep


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
    meta_path: str | Path,
    output_dir: str | Path,
    include_source_prep: bool = True,
    project_root: str | Path | None = None,
    plate_specs_path: str | Path | None = None,
):
    """
    Execute the pipeline against explicit input files and output directory.

    This entrypoint is suitable for the web app because it keeps each run isolated
    and does not depend on mutating repository input/config files.
    """
    root = find_project_root(project_root)
    cfg = validate_config_dict(dict(config))

    explicit_layout_path = Path(layout_path)
    explicit_meta_path = Path(meta_path)
    explicit_plate_specs_path = (
        Path(plate_specs_path)
        if plate_specs_path is not None
        else Path(root) / "data" / "source_plate_specs.json"
    )
    output_paths = build_output_paths(Path(output_dir), cfg)

    paths = {
        "project_root": Path(root),
        "layout_path": explicit_layout_path,
        "meta_path": explicit_meta_path,
        "plate_specs_path": explicit_plate_specs_path,
        "out_idot": output_paths["out_idot"],
        "out_liquids": output_paths["out_liquids"],
        "run_timestamp": str(output_paths["run_timestamp"]),
    }

    return _run_pipeline_with_resolved_inputs(
        root=Path(root),
        cfg=cfg,
        paths=paths,
        include_source_prep=include_source_prep,
    )


def _run_pipeline_with_resolved_inputs(*, root: Path, cfg: dict, paths: dict, include_source_prep: bool):
    """Execute the shared pipeline workflow once config and file paths are resolved."""

    specs = load_source_plate_specs(paths["plate_specs_path"])
    source_specs = get_source_plate_spec(specs, cfg["sourceplate_type"])

    # Load and normalize input data
    df = load_layout_csv(paths["layout_path"])
    df, _ = normalize_layout_df(df)

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
    liquid_table, liquid_table_export = build_liquid_table(all_rows, str(cfg["protocol_name"]))
    
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
    
    all_rows = attach_and_sort_dispense_rows(all_rows, liquid_table, liquid_table_export)

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

    # Validation
    preview_df, header_row_idx = validate_export_file(
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

    # Source plate preparation (optional)
    source_prep_volumes = None
    source_prep_instructions = None
    if include_source_prep:
        source_prep_volumes, source_prep_instructions = source_plate_prep.generate_source_plate_prep_instructions(
            Path(paths["project_root"]) / "outputs" / "results",
            cfg,
            paths["meta_path"],
            paths["plate_specs_path"],
            cfg["protocol_name"],
            cfg["layout_file"],
            idot_csv_path=paths["out_idot"],
            liquids_csv_path=paths["out_liquids"],
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
        "preview_df": preview_df,
        "header_row_idx": header_row_idx,
        "is_solvent_control_count": int(df["is_solvent_control"].fillna(False).astype(bool).sum()),
        "solvent_caps": solvent_caps,
        "solvent_summary": validated_solvent_summary or solvent_summary,
        "target_dmso_ul": validated_target_dmso_ul,
        "max_dmso_ul": validated_max_dmso_ul,
        "source_prep_volumes": source_prep_volumes,
        "source_prep_instructions": source_prep_instructions,
    }
