"""
Utility to generate MiniZinc .dzn files directly (without using Python API).
Useful for direct MiniZinc CLI usage.
"""

import argparse
import json
from pathlib import Path


def generate_dzn_from_json(json_path: str, output_path: str) -> None:
    """
    Generate .dzn file from JSON configuration.
    
    Args:
        json_path: Path to JSON config file
        output_path: Output path for .dzn file
    """
    with open(json_path, 'r') as f:
        config = json.load(f)
    
    dzn_content = generate_dzn_content(config)
    
    with open(output_path, 'w') as f:
        f.write(dzn_content)
    
    print(f"Generated: {output_path}")


def generate_dzn_content(config: dict) -> str:
    """Generate .dzn file content from configuration dict."""
    lines = []
    
    # Plate configuration
    lines.append(f"num_rows = {config['plate_rows']};")
    lines.append(f"num_cols = {config['plate_cols']};")
    lines.append(f"size_empty_edge = {config.get('empty_edge', 1)};")
    lines.append(f"horizontal_cell_lines = {config.get('horizontal_cell_lines', 1)};")
    lines.append(f"vertical_cell_lines = {config.get('vertical_cell_lines', 1)};")
    lines.append(f"allow_empty_wells = {str(config.get('allow_empty_wells', True)).lower()};")
    lines.append("")
    
    # Constraints
    lines.append(f"concentrations_on_different_rows = {str(config.get('concentrations_on_different_rows', True)).lower()};")
    lines.append(f"concentrations_on_different_columns = {str(config.get('concentrations_on_different_columns', True)).lower()};")
    lines.append(f"replicates_on_same_plate = {str(config.get('replicates_on_same_plate', True)).lower()};")
    lines.append(f"replicates_on_different_plates = {str(config.get('replicates_on_different_plates', False)).lower()};")
    lines.append(f"force_spread_controls = {str(config.get('force_spread_controls', False)).lower()};")
    lines.append(f"force_spread_concentrations = {str(config.get('force_spread_concentrations', False)).lower()};")
    lines.append("")
    
    # Compounds
    compounds = config.get('compounds', [])
    lines.append(f"compounds = {len(compounds)};")
    
    if compounds:
        rep_list = ", ".join(str(c['replicates']) for c in compounds)
        lines.append(f"compound_replicates = [{rep_list}];")
        
        conc_list = ", ".join(str(c['concentrations']) for c in compounds)
        lines.append(f"compound_concentrations = [{conc_list}];")
        
        names = ", ".join(f'"{c["name"]}"' for c in compounds)
        lines.append(f'compound_names = [{names}];')
        
        # Concentration names
        conc_name_rows = []
        for compound in compounds:
            c_names = compound.get('concentration_names', [f'Conc_{i+1}' for i in range(compound['concentrations'])])
            names = ", ".join(f'"{name}"' for name in c_names)
            conc_name_rows.append(names)
        conc_names_str = "|".join(conc_name_rows)
        lines.append(f'compound_concentration_names = [|{conc_names_str}|];')
    else:
        lines.append("compound_replicates = [];")
        lines.append("compound_concentrations = [];")
        lines.append("compound_names = [];")
        lines.append("compound_concentration_names = [];")
    
    max_conc = max([c['concentrations'] for c in compounds], default=1)
    lines.append(f'compound_concentration_indicators = ["" | i in 1..{max_conc}];')
    lines.append("")
    
    # Combinations (deprecated)
    lines.append("combinations = 0;")
    lines.append("combination_concentrations = 0;")
    lines.append("combination_names = [];")
    lines.append("combination_concentration_names = [];")
    lines.append("")
    
    # Controls
    controls = config.get('controls', [])
    lines.append(f"num_controls = {len(controls)};")
    
    if controls:
        rep_list = ", ".join(str(c['replicates']) for c in controls)
        lines.append(f"control_replicates = [{rep_list}];")
        
        conc_list = ", ".join(str(c['concentration_levels']) for c in controls)
        lines.append(f"control_concentrations = [{conc_list}];")
        
        names = ", ".join(f'"{c["name"]}"' for c in controls)
        lines.append(f'control_names = [{names}];')
        
        # Control concentration names
        conc_name_rows = []
        for control in controls:
            c_names = control.get('concentration_names', [f'{control["name"]}_conc_{i+1}' for i in range(control['concentration_levels'])])
            names = ", ".join(f'"{name}"' for name in c_names)
            conc_name_rows.append(names)
        conc_names_str = "|".join(conc_name_rows)
        lines.append(f'control_concentration_names = [|{conc_names_str}|];')
    else:
        lines.append("control_replicates = [];")
        lines.append("control_concentrations = [];")
        lines.append("control_names = [];")
        lines.append("control_concentration_names = [];")
    
    lines.append("")
    
    # Advanced control parameters
    lines.append(f"balance_controls_inside_plate = {str(config.get('balance_controls_inside_plate', True)).lower()};")
    lines.append(f"interconnected_plates = {str(config.get('interconnected_plates', True)).lower()};")
    lines.append(f"control_slack = {config.get('control_slack', 0)};")
    
    # Testing parameters (optional)
    if config.get('testing', False):
        lines.append(f"testing = true;")
    if config.get('sorted_compounds') is not None:
        lines.append(f"sorted_compounds = {str(config.get('sorted_compounds')).lower()};")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate MiniZinc .dzn files from JSON configuration"
    )
    parser.add_argument("json_file", help="Input JSON configuration file")
    parser.add_argument("-o", "--output", help="Output .dzn file (default: <input>.dzn)")
    
    args = parser.parse_args()
    
    input_path = Path(args.json_file)
    if not input_path.exists():
        print(f"Error: {input_path} not found")
        return
    
    output_path = args.output or str(input_path.with_suffix('.dzn'))
    
    generate_dzn_from_json(str(input_path), output_path)


if __name__ == "__main__":
    main()
