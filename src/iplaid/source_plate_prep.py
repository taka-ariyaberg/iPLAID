"""
Source plate preparation planning module.

Calculates prep volumes for source plates by standardizing on 1 mL per concentration,
determining appropriate fill volumes for source wells, and generating practical
preparation instructions with dilution recipes and source well assignments.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np

from .download_filenames import (
    build_project_details,
    build_source_prep_output_path,
    find_latest_download_artifact,
)


def parse_liquid_name(liquid_name: str) -> Tuple[str, float]:
    """
    Parse iDOT liquid name format: [CompoundName][Concentration]
    
    Returns:
        Tuple of (compound_name, concentration_mM)
    """
    match = re.match(r'\[([^\]]+)\]\[([^\]]+)\]', liquid_name)
    if not match:
        raise ValueError(f"Cannot parse liquid name: {liquid_name}")
    
    compound_name = match.group(1)
    concentration_str = match.group(2)
    
    try:
        concentration_mM = float(concentration_str)
    except ValueError:
        raise ValueError(f"Cannot parse concentration from: {concentration_str}")
    
    return compound_name, concentration_mM


def load_meta_file(meta_path: Path) -> Dict[str, Dict[str, any]]:
    """
    Load compound metadata (stock concentrations, solvents).
    
    Returns:
        Dict mapping compound_name -> {highest_stock_mM, solvent}
    """
    df = pd.read_csv(meta_path)
    meta = {}
    for _, row in df.iterrows():
        meta[row['cmpdname']] = {
            'highest_stock_mM': row['highest_stock_mM'],
            'solvent': row['solvent']
        }
    return meta


def load_dead_volume(plate_specs_path: Path, sourceplate_type: str) -> float:
    """
    Load dead volume for the sourceplate type.
    
    Returns:
        Dead volume in µL
    """
    with open(plate_specs_path) as f:
        specs = json.load(f)
    
    if sourceplate_type not in specs:
        raise ValueError(f"Unknown sourceplate_type: {sourceplate_type}")
    
    return specs[sourceplate_type]['dead_volume_uL_aq_lt']


def get_well_capacity(plate_specs_path: Path, sourceplate_type: str) -> float:
    """
    Get effective reservoir volume for the sourceplate type.
    
    Returns:
        Well capacity in µL
    """
    with open(plate_specs_path) as f:
        specs = json.load(f)
    
    if sourceplate_type not in specs:
        raise ValueError(f"Unknown sourceplate_type: {sourceplate_type}")
    
    return specs[sourceplate_type]['effective_reservoir_uL']


def sum_volumes_per_compound(idot_csv_path: Path, liquids_csv_path: Path) -> Dict[Tuple[str, float], Dict]:
    """
    Calculate total volume needed per compound/concentration and map to source wells.
    
    Returns:
        Dict mapping (compound_name, concentration_mM) -> {
            'dispense_volume_uL': float,
            'source_well': str
        }
    """
    # Load main protocol CSV
    df_protocol = pd.read_csv(idot_csv_path, skiprows=3)
    
    # Load liquids CSV to map liquid names to compound/concentration and source wells
    df_liquids = pd.read_csv(liquids_csv_path)
    
    # Create mapping from liquid name to (compound, concentration, source_well)
    liquid_to_info = {}
    for _, row in df_liquids.iterrows():
        liquid_name = row['Liquid Name'].strip()
        source_well = row['Source Well'].strip()
        compound, concentration = parse_liquid_name(liquid_name)
        liquid_to_info[liquid_name] = {
            'compound': compound,
            'concentration': concentration,
            'source_well': source_well
        }
    
    # Sum volumes per compound/concentration
    volumes = {}
    for _, row in df_protocol.iterrows():
        liquid_name = row['Liquid Name'].strip()
        volume_ul = float(row['Volume [uL]'])
        
        if liquid_name in liquid_to_info:
            info = liquid_to_info[liquid_name]
            compound = info['compound']
            concentration = info['concentration']
            source_well = info['source_well']
            
            key = (compound, concentration)
            if key not in volumes:
                volumes[key] = {
                    'dispense_volume_uL': 0,
                    'source_well': source_well
                }
            volumes[key]['dispense_volume_uL'] += volume_ul

    return volumes


def aggregate_dispenses_per_stock(
    all_rows: pd.DataFrame,
    liquid_table: pd.DataFrame,
) -> Dict[Tuple[str, float], Dict]:
    """In-memory replacement for sum_volumes_per_compound. Aggregates dispense
    volume per (compound, stock_concentration_mM) from the pipeline's canonical
    dispense dataframes — no dispenser-specific CSV parsing.

    Solvent-topup liquids (concentration == 0) are filtered out: they are
    carrier dispenses, not compound stocks needing preparation.

    Args:
        all_rows: Post-rounding, post-exclusion dispense rows. Must carry
            'Liquid Name' (format "[cmpdname][stock_mM]") and 'Volume [uL]'.
        liquid_table: Mapping of unique Liquid Name -> Source Plate / Source Well.
            Must carry 'Liquid Name' and 'Source Well'.

    Returns:
        Dict[(compound_name, stock_concentration_mM)] -> {
            'dispense_volume_uL': float (total across all dispense rows for this stock),
            'source_well': str,
        }
        Shape is identical to sum_volumes_per_compound, so downstream
        group_compounds_by_name and generate_instructions work unchanged.
    """
    liquid_to_info: Dict[str, Dict] = {}
    for _, row in liquid_table.iterrows():
        liquid_name = str(row['Liquid Name']).strip()
        source_well = str(row['Source Well']).strip()
        compound, concentration = parse_liquid_name(liquid_name)
        if concentration == 0:
            continue
        liquid_to_info[liquid_name] = {
            'compound': compound,
            'concentration': concentration,
            'source_well': source_well,
        }

    volumes: Dict[Tuple[str, float], Dict] = {}
    for _, row in all_rows.iterrows():
        liquid_name = str(row['Liquid Name']).strip()
        info = liquid_to_info.get(liquid_name)
        if info is None:
            continue
        key = (info['compound'], info['concentration'])
        if key not in volumes:
            volumes[key] = {
                'dispense_volume_uL': 0.0,
                'source_well': info['source_well'],
            }
        volumes[key]['dispense_volume_uL'] += float(row['Volume [uL]'])

    return volumes


def calculate_actual_needed_volume(
    dispense_volume: float,
    dead_volume: float,
    overage_pct: float
) -> float:
    """
    Calculate total volume actually needed for this compound.
    """
    return dispense_volume * (1 + overage_pct) + dead_volume


def calculate_fill_volume(
    well_capacity: float,
    fill_pct: float
) -> float:
    """
    Calculate how much to put in a source well based on capacity and fill percentage.
    """
    return well_capacity * fill_pct


def calculate_dilution_to_prepare(
    target_concentration: float,
    stock_concentration: float,
    prep_volume: float,
    solvent: str
) -> Dict[str, any]:
    """
    Calculate stock and solvent volumes to prepare target concentration.
    
    Returns:
        Dict with 'stock_volume', 'solvent_volume', 'description'
    """
    if stock_concentration == 0:
        # Pure solvent
        return {
            'stock_volume_uL': prep_volume,
            'solvent_volume_uL': 0,
            'dilution_factor': 1.0,
            'description': f'Use pure {solvent}',
            'is_pure_solvent': True
        }
    
    dilution_factor = stock_concentration / target_concentration
    stock_volume = prep_volume / dilution_factor
    solvent_volume = prep_volume - stock_volume
    
    return {
        'stock_volume_uL': stock_volume,
        'solvent_volume_uL': solvent_volume,
        'dilution_factor': dilution_factor,
        'description': f'Take {stock_volume:.2f} µL of stock ({stock_concentration:g} mM) + {solvent_volume:.2f} µL {solvent}',
        'is_pure_solvent': False
    }


def group_compounds_by_name(
    volumes_per_compound: Dict[Tuple[str, float], Dict]
) -> Dict[str, List[Dict]]:
    """
    Group preparations by compound name, sorted by concentration.
    
    Returns:
        Dict mapping compound_name -> list of prep infos sorted by concentration
    """
    grouped = {}
    for (compound_name, concentration), vol_info in volumes_per_compound.items():
        if compound_name not in grouped:
            grouped[compound_name] = []
        grouped[compound_name].append({
            'concentration_mM': concentration,
            'dispense_volume_uL': vol_info['dispense_volume_uL'],
            'source_well': vol_info['source_well']
        })
    
    # Sort by concentration (ascending) for each group
    for compound_name in grouped:
        grouped[compound_name].sort(key=lambda x: x['concentration_mM'])
    
    return grouped


def generate_instructions(
    grouped_compounds: Dict[str, List[Dict]],
    meta: Dict[str, Dict[str, any]],
    dead_volume: float,
    overage_pct: float,
    prep_volume: float,
    fill_pct: float,
    well_capacity: float
) -> str:
    """
    Generate human-friendly preparation instructions.
    """
    lines = []
    lines.append("=" * 90)
    lines.append("SOURCE PLATE PREPARATION INSTRUCTIONS")
    lines.append("=" * 90)
    lines.append("")
    lines.append(f"Standard preparation: 1.0 mL per concentration")
    lines.append(f"Source well fill level: {fill_pct*100:.0f}% of {well_capacity:.0f} µL capacity = {calculate_fill_volume(well_capacity, fill_pct):.0f} µL per well")
    lines.append("")
    
    for compound_name in sorted(grouped_compounds.keys()):
        preparations = grouped_compounds[compound_name]
        stock_info = meta.get(compound_name, {})
        stock_concentration = stock_info.get('highest_stock_mM', 0)
        solvent = stock_info.get('solvent', 'DMSO')
        
        lines.append(f"\n{'='*90}")
        lines.append(f"COMPOUND: {compound_name}")
        lines.append(f"{'='*90}")
        
        if len(preparations) == 1:
            # Single concentration
            prep = preparations[0]
            lines.extend(_format_single_prep(
                prep, compound_name, stock_concentration, solvent,
                dead_volume, overage_pct, prep_volume, fill_pct, well_capacity
            ))
        else:
            # Multiple concentrations - show as series
            lines.extend(_format_dilution_series(
                preparations, compound_name, stock_concentration, solvent,
                dead_volume, overage_pct, prep_volume, fill_pct, well_capacity
            ))
    
    lines.append("\n" + "=" * 90)
    return "\n".join(lines)


def _format_single_prep(
    prep: Dict, compound_name: str, stock_concentration: float, solvent: str,
    dead_volume: float, overage_pct: float, prep_volume: float, 
    fill_pct: float, well_capacity: float
) -> List[str]:
    """Format preparation for a single concentration."""
    lines = []
    
    concentration = prep['concentration_mM']
    dispense_vol = prep['dispense_volume_uL']
    source_well = prep['source_well']
    
    # Calculate actual volume needed
    actual_needed = calculate_actual_needed_volume(dispense_vol, dead_volume, overage_pct)
    
    # Calculate what to prepare
    dilution = calculate_dilution_to_prepare(concentration, stock_concentration, prep_volume, solvent)
    
    # Calculate fill volume
    fill_volume = calculate_fill_volume(well_capacity, fill_pct)
    
    lines.append(f"\nTarget concentration: {concentration} mM")
    lines.append(f"Actual volume needed: {actual_needed:.2f} µL (dispense: {dispense_vol:.2f} µL + overage: {dispense_vol * overage_pct:.2f} µL + dead volume: {dead_volume:.2f} µL)")
    lines.append("")
    
    if dilution['is_pure_solvent']:
        lines.append(f"PREPARATION (1.0 mL):")
        lines.append(f"  {dilution['description']}")
    else:
        lines.append(f"PREPARATION (1.0 mL):")
        lines.append(f"  {dilution['description']}")
    
    lines.append("")
    lines.append(f"SOURCE WELL ASSIGNMENT:")
    lines.append(f"  Fill source well {source_well} with {fill_volume:.0f} µL")
    lines.append(f"  (only {actual_needed:.2f} µL will be used, {fill_volume - actual_needed:.2f} µL excess for storage)")
    
    return lines


def _format_dilution_series(
    preparations: List[Dict], compound_name: str, stock_concentration: float, solvent: str,
    dead_volume: float, overage_pct: float, prep_volume: float,
    fill_pct: float, well_capacity: float
) -> List[str]:
    """Format preparation for multiple concentrations as a series."""
    lines = []
    
    fill_volume = calculate_fill_volume(well_capacity, fill_pct)
    
    lines.append(f"\nMultiple concentrations - Dilution Series:")
    lines.append("")
    
    for i, prep in enumerate(preparations, 1):
        concentration = prep['concentration_mM']
        dispense_vol = prep['dispense_volume_uL']
        source_well = prep['source_well']
        
        actual_needed = calculate_actual_needed_volume(dispense_vol, dead_volume, overage_pct)
        
        dilution = calculate_dilution_to_prepare(concentration, stock_concentration, prep_volume, solvent)
        
        lines.append(f"STEP {i}: Prepare {concentration} mM")
        lines.append(f"  Recipe: {dilution['description']}")
        lines.append(f"  → Fill source well {source_well} with {fill_volume:.0f} µL")
        lines.append(f"     (need {actual_needed:.2f} µL, excess {fill_volume - actual_needed:.2f} µL)")
        lines.append("")
    
    lines.append(f"RECOMMENDATION: Prepare highest concentration first, then dilute down")
    lines.append(f"(e.g., prepare {preparations[-1]['concentration_mM']} mM, dilute to get lower concentrations)")
    
    return lines


def format_prep_warnings_header(
    *,
    scatter_warnings: list[dict],
    excluded: list[dict],
) -> str:
    """Return a header section for the prep text file, or empty string if no warnings.

    Args:
        scatter_warnings: list of {"compound": str, "wells": tuple[str, ...]} dicts.
        excluded: list of {"compound": str, "stocks_needed": int, "free_wells_remaining": int} dicts.
    """
    if not scatter_warnings and not excluded:
        return ""
    lines: list[str] = ["=" * 72]
    if excluded:
        lines.append(
            "NOTE: these compounds were dropped — the source plate is full. They are"
        )
        lines.append(
            "NOT in this protocol; their destination wells will stay empty."
        )
        lines.append("")
        for ew in excluded:
            lines.append(
                f"   • {ew['compound']}  (needed {ew['stocks_needed']} wells, "
                f"only {ew['free_wells_remaining']} free)"
            )
    if scatter_warnings:
        if excluded:
            lines.append("")
        lines.append(
            "NOTE: these compounds didn't fit the standard layout — their stocks are"
        )
        lines.append(
            "in scattered wells. Fill each well below individually."
        )
        lines.append("")
        for sw in scatter_warnings:
            wells_str = ", ".join(sw["wells"])
            lines.append(f"   • {sw['compound']}: {wells_str}")
    lines.append("=" * 72)
    lines.append("")
    return "\n".join(lines)


def generate_source_plate_prep_instructions(
    output_dir: Path,
    config: Dict,
    meta_path: Path,
    plate_specs_path: Path,
    protocol_name: str,
    layout_file: str,
    idot_csv_path: Optional[Path] = None,
    liquids_csv_path: Optional[Path] = None,
    scatter_warnings: Optional[list[dict]] = None,
    excluded: Optional[list[dict]] = None,
    all_rows: Optional[pd.DataFrame] = None,
    liquid_table: Optional[pd.DataFrame] = None,
) -> Tuple[Dict, str]:
    """Generate source plate preparation instructions.

    Two data sources are supported (mutually exclusive in practice):

    - **In-memory (preferred, dispenser-agnostic):** pass `all_rows` and
      `liquid_table`. Aggregation reads from these in-memory dataframes and
      makes no assumption about the dispenser's CSV shape. Used by the
      pipeline for both iDOT and Echo runs.
    - **Legacy CSV (back-compat for notebook/CLI):** pass `idot_csv_path` and
      `liquids_csv_path` (or leave them None to auto-detect from `output_dir`).
      Reads volumes back from the iDOT-shaped protocol CSV. Only works for
      iDOT-format CSVs.

    Steps 2 and 3 (`group_compounds_by_name`, `generate_instructions`) are
    dispenser-agnostic and produce the same TXT format regardless of data source.

    Returns:
        Tuple of (prep_volumes_dict, instructions_text).
    """
    # --- Step 1: per-(compound, concentration) volume aggregation ---
    if all_rows is not None and liquid_table is not None:
        # In-memory path — no CSV round-trip.
        volumes_per_compound = aggregate_dispenses_per_stock(all_rows, liquid_table)
    else:
        # Legacy CSV path — auto-detect file paths if not provided.
        if idot_csv_path is None or liquids_csv_path is None:
            project_details = build_project_details(
                config.get("user_name", "user"),
                protocol_name,
            )
            if idot_csv_path is None:
                idot_csv_path = find_latest_download_artifact(
                    output_dir,
                    artifact="idot_protocol",
                    extension=".csv",
                    project_details=project_details,
                )
            if liquids_csv_path is None:
                liquids_csv_path = find_latest_download_artifact(
                    output_dir,
                    artifact="liquids_map",
                    extension=".csv",
                    project_details=project_details,
                )
            layout_base = Path(layout_file).stem
            if idot_csv_path is None:
                idot_csv_path = output_dir / f"IDOT_{protocol_name}__{layout_base}.csv"
            if liquids_csv_path is None:
                liquids_csv_path = output_dir / f"iDOT_liquids_{protocol_name}__{layout_base}.csv"
        idot_csv = idot_csv_path
        liquids_csv = liquids_csv_path
        if not idot_csv.exists():
            raise FileNotFoundError(f"iDOT protocol file not found: {idot_csv}")
        if not liquids_csv.exists():
            raise FileNotFoundError(f"Liquids mapping file not found: {liquids_csv}")
        volumes_per_compound = sum_volumes_per_compound(idot_csv, liquids_csv)

    # --- Common shared logic (unchanged from the previous version) ---
    meta = load_meta_file(meta_path)
    dead_volume = load_dead_volume(plate_specs_path, config['sourceplate_type'])
    well_capacity = get_well_capacity(plate_specs_path, config['sourceplate_type'])

    # Group by compound name
    grouped_compounds = group_compounds_by_name(volumes_per_compound)

    # Generate instructions
    instructions = generate_instructions(
        grouped_compounds,
        meta,
        dead_volume,
        config['source_prep_overage_pct'],
        config['standard_prep_volume_uL'],
        config['source_well_fill_pct'],
        well_capacity
    )

    # Prepend Tier 2/3 warnings header (empty string if no warnings).
    header = format_prep_warnings_header(
        scatter_warnings=scatter_warnings or [],
        excluded=excluded or [],
    )
    instructions = header + instructions

    return volumes_per_compound, instructions


def generate_existing_source_plate_summary(
    *,
    config: Dict,
    source_layout: pd.DataFrame,
    liquid_table: pd.DataFrame,
    all_rows: pd.DataFrame,
    source_layout_name: Optional[str] = None,
) -> Tuple[List[Dict], str]:
    """
    Generate a run summary when the user supplied an existing source plate.

    The uploaded source layout is treated as the source of truth for source
    plate/well positions. This summary reports how iPLAID used that plate; it
    intentionally does not provide source-plate preparation recipes.
    """
    usage = all_rows.copy()
    usage["Volume [uL]"] = usage["Volume [uL]"].astype(float)
    usage["_target_well_key"] = (
        usage["Target Plate"].astype(str) + ":" + usage["Target Well"].astype(str)
    )
    usage_summary = (
        usage
        .groupby(["Liquid Name", "Source Plate", "Source Well"], dropna=False)
        .agg(
            dispense_count=("Volume [uL]", "size"),
            total_dispense_uL=("Volume [uL]", "sum"),
            target_well_count=("_target_well_key", "nunique"),
        )
        .reset_index()
    )
    usage_summary["total_dispense_nL"] = usage_summary["total_dispense_uL"] * 1000.0

    base_columns = [
        "Liquid Name",
        "compound",
        "stock_mM",
        "is_control_liquid",
        "Source Plate",
        "Source Well",
    ]
    summary = (
        liquid_table[base_columns]
        .drop_duplicates()
        .merge(
            usage_summary,
            on=["Liquid Name", "Source Plate", "Source Well"],
            how="left",
        )
        .fillna({
            "dispense_count": 0,
            "total_dispense_uL": 0.0,
            "target_well_count": 0,
            "total_dispense_nL": 0.0,
        })
        .sort_values(["Source Plate", "Source Well", "Liquid Name"], kind="mergesort")
        .reset_index(drop=True)
    )

    source_layout_clean = source_layout.copy()
    if "Liquid Name" in source_layout_clean.columns:
        source_layout_clean["Liquid Name"] = source_layout_clean["Liquid Name"].astype(str).str.strip()
    required_liquids = set(liquid_table["Liquid Name"].astype(str))
    if "Liquid Name" in source_layout_clean.columns:
        unused_layout = source_layout_clean.loc[
            ~source_layout_clean["Liquid Name"].isin(required_liquids)
        ].copy()
    else:
        unused_layout = pd.DataFrame()

    records = summary.to_dict("records")

    lines: List[str] = []
    lines.append("SOURCE PLATE LAYOUT SUMMARY")
    lines.append("")
    lines.append("Uploaded source plate layout was used as the source of truth for this run.")
    lines.append("iPLAID calculated target concentrations, transfer volumes, solvent top-ups,")
    lines.append("protocol rows, and iMETA from the run inputs, then mapped each required")
    lines.append("liquid to the source plate/well provided in the uploaded layout.")
    lines.append("")
    lines.append("This file is a usage summary, not a preparation recipe.")
    lines.append("The physical source plate must already contain the listed liquids at the")
    lines.append("listed stock concentrations. The user is responsible for ensuring each")
    lines.append("source well contains enough volume for the total dispense demand below.")
    lines.append("")
    lines.append("Run")
    lines.append(f"  Protocol: {config.get('protocol_name', '')}")
    lines.append(f"  User: {config.get('user_name', '')}")
    lines.append(f"  Dispenser: {config.get('dispenser', 'idot')}")
    lines.append(f"  Source plate type: {config.get('sourceplate_type', '')}")
    if source_layout_name:
        lines.append(f"  Uploaded source layout file: {source_layout_name}")
    lines.append(f"  Required liquids matched: {len(summary)}")
    lines.append(f"  Source plates referenced: {summary['Source Plate'].nunique()}")
    lines.append("")
    lines.append("Required source wells")
    lines.append(
        "Liquid Name,Source Plate,Source Well,Compound,Stock mM,"
        "Dispense count,Target well count,Total dispense uL,Total dispense nL"
    )
    for _, row in summary.iterrows():
        stock = "" if bool(row["is_control_liquid"]) else f"{float(row['stock_mM']):g}"
        lines.append(
            f"{row['Liquid Name']},{row['Source Plate']},{row['Source Well']},"
            f"{row['compound']},{stock},{int(row['dispense_count'])},"
            f"{int(row['target_well_count'])},{float(row['total_dispense_uL']):.6f},"
            f"{float(row['total_dispense_nL']):.3f}"
        )

    if len(unused_layout) > 0:
        lines.append("")
        lines.append("Unused uploaded source-layout entries")
        columns = [col for col in ["Liquid Name", "Source Plate", "Source Well"] if col in unused_layout.columns]
        lines.append(",".join(columns))
        for _, row in unused_layout[columns].iterrows():
            lines.append(",".join(str(row[col]) for col in columns))

    lines.append("")
    return records, "\n".join(lines)


def run(project_root: Path) -> None:
    """
    Main entry point: generate source prep instructions from project outputs.
    """
    # Load config
    config_path = project_root / 'config' / 'config.json'
    with open(config_path) as f:
        config = json.load(f)
    
    # Define paths
    output_dir = project_root / 'outputs' / 'results'
    meta_path = project_root / 'inputs' / 'meta' / config['meta_file']
    plate_specs_path = project_root / 'data' / 'idot_source_plate_specs.json'
    
    # Generate instructions
    prep_volumes, instructions = generate_source_plate_prep_instructions(
        output_dir,
        config,
        meta_path,
        plate_specs_path,
        config['protocol_name'],
        config['layout_file']
    )
    
    # Write to output file
    output_file = build_source_prep_output_path(output_dir, config)
    with open(output_file, 'w') as f:
        f.write(instructions)
    
    print(f"Source plate preparation instructions written to: {output_file}")
    print(instructions)


if __name__ == '__main__':
    import sys
    project_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    run(project_root)
