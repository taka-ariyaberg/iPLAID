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


def generate_source_plate_prep_instructions(
    output_dir: Path,
    config: Dict,
    meta_path: Path,
    plate_specs_path: Path,
    protocol_name: str,
    layout_file: str,
    idot_csv_path: Optional[Path] = None,
    liquids_csv_path: Optional[Path] = None
) -> Tuple[Dict, str]:
    """
    Generate source plate preparation instructions from iDOT outputs.
    
    Args:
        output_dir: Output directory
        config: Configuration dictionary
        meta_path: Path to compound metadata file
        plate_specs_path: Path to plate specifications file
        protocol_name: Protocol name
        layout_file: Layout file name
        idot_csv_path: Optional explicit path to iDOT protocol CSV (auto-detected if None)
        liquids_csv_path: Optional explicit path to liquids CSV (auto-detected if None)
    
    Returns:
        Tuple of (prep_volumes_dict, instructions_text)
    """
    # Use provided paths or auto-detect based on naming convention
    if idot_csv_path is None or liquids_csv_path is None:
        layout_base = Path(layout_file).stem  # e.g., "Layout_1"
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
    
    # Load all necessary data
    meta = load_meta_file(meta_path)
    dead_volume = load_dead_volume(plate_specs_path, config['sourceplate_type'])
    well_capacity = get_well_capacity(plate_specs_path, config['sourceplate_type'])
    
    # Calculate volumes
    volumes_per_compound = sum_volumes_per_compound(idot_csv, liquids_csv)
    
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
    
    return volumes_per_compound, instructions


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
    plate_specs_path = project_root / 'data' / 'source_plate_specs.json'
    
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
    output_file = output_dir / f"source_plate_prep_{config['protocol_name']}__{Path(config['layout_file']).stem}.txt"
    with open(output_file, 'w') as f:
        f.write(instructions)
    
    print(f"Source plate preparation instructions written to: {output_file}")
    print(instructions)


if __name__ == '__main__':
    import sys
    project_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    run(project_root)
