"""
Pre-flight Validation Module

Validates that all requested concentration-stock combinations are feasible
before running the pipeline. Calculates minimum requirements and suggests
configuration adjustments if needed.

Accounts for stock dilution series (10mM → 1mM → 0.1mM → etc).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def get_min_pipette_volume_nl(sourceplate_type: str) -> float:
    """Get minimum pipette volume for source plate type in nanoliters."""
    return 30.0 if sourceplate_type == "S.200" else 8.0


def calculate_required_dmso_pct(
    target_conc_um: float,
    highest_stock_mm: float,
    working_volume_ul: float,
    sourceplate_type: str,
) -> tuple[bool, float|None, str]:
    """
    Calculate feasibility and required DMSO% for a target concentration.
    
    Tries all stocks in the dilution series to find the minimum DMSO% needed.
    
    Returns:
        (is_feasible, min_dmso_pct_needed, reason)
    """
    
    if highest_stock_mm == 0:
        return True, 0.0, "Control/DMSO"
    if target_conc_um == 0:
        return True, 0.0, "Zero target"
    
    min_pipette_nl = get_min_pipette_volume_nl(sourceplate_type)
    
    # Generate dilution series
    lowest_stock_mM = 0.0000001
    availstocks_mM = [
        highest_stock_mm / (10 ** x)
        for x in range(int(np.ceil(np.log10(highest_stock_mm / lowest_stock_mM))) + 1)
    ]
    
    # Try each stock to find minimum DMSO% needed
    min_dmso_pct = 999.0
    best_stock = None
    
    for stock_mm in availstocks_mM:
        # C1_high = (V2 * target) / Min V1 = max stock that can be used
        C1_high = (working_volume_ul * target_conc_um) / min_pipette_nl
        
        if stock_mm > C1_high:
            continue  # Stock too concentrated
        
        # dmso% >= (target * 100) / (stock * 1000)
        dmso_needed = (target_conc_um * 100) / (stock_mm * 1000)
        
        if dmso_needed <= 100 and dmso_needed < min_dmso_pct:
            min_dmso_pct = dmso_needed
            best_stock = stock_mm
    
    if best_stock is None:
        return False, None, "No stock in series achieves this concentration"
    
    return True, min_dmso_pct, f"Requires >= {min_dmso_pct:.3f}% DMSO"


def validate_all_concentrations(
    df: pd.DataFrame,
    highest_stock_mm: float,
    working_volume_ul: float,
    sourceplate_type: str,
    current_dmso_pct: float,
) -> dict:
    """Validate all compound-concentration pairs."""
    
    unique_pairs = df.groupby(['cmpdname', 'CONCuM']).size().reset_index(name='count')
    
    issues = []
    requirements = []
    max_required_dmso = current_dmso_pct
    
    for _, row in unique_pairs.iterrows():
        compound = row['cmpdname']
        target_conc = float(str(row['CONCuM']).strip().replace('"', ''))
        count = row['count']
        
        is_feasible, required_dmso, reason = calculate_required_dmso_pct(
            target_conc,
            highest_stock_mm,
            working_volume_ul,
            sourceplate_type,
        )
        
        req_info = {
            'compound': compound,
            'target_conc_um': target_conc,
            'feasible': is_feasible,
            'required_dmso_pct': required_dmso,
            'reason': reason,
            'well_count': count,
        }
        requirements.append(req_info)
        
        if not is_feasible:
            issues.append(
                f"  ❌ {compound} @ {target_conc:.4g} µM: {reason} ({count} wells)"
            )
        elif required_dmso is not None and required_dmso > current_dmso_pct:
            issues.append(
                f"  ⚠️  {compound} @ {target_conc:.4g} µM: "
                f"needs {required_dmso:.3f}% DMSO but configured {current_dmso_pct:.1f}% ({count} wells)"
            )
        
        if required_dmso is not None:
            max_required_dmso = max(max_required_dmso, required_dmso)
    
    all_feasible = all(x['feasible'] for x in requirements)
    
    return {
        'all_feasible': all_feasible,
        'required_dmso_pct': max_required_dmso,
        'issues': issues,
        'requirements': requirements,
        'current_dmso_pct': current_dmso_pct,
    }


def print_preflight_report(validation_result: dict) -> bool:
    """Print validation report. Returns True if pipeline should proceed."""
    
    issues = validation_result['issues']
    feasible = validation_result['all_feasible']
    current_dmso = validation_result['current_dmso_pct']
    required_dmso = validation_result['required_dmso_pct']
    reqs = validation_result['requirements']
    
    # Statistics
    total_pairs = len(reqs)
    feasible_count = sum(1 for r in reqs if r['feasible'])
    warning_count = sum(1 for r in reqs if r['feasible'] and r['required_dmso_pct'] and r['required_dmso_pct'] > current_dmso)
    error_count = sum(1 for r in reqs if not r['feasible'])
    
    print("\n" + "="*90)
    print("PRE-FLIGHT VALIDATION: Concentration Feasibility Analysis")
    print("="*90)
    
    print(f"\nConfiguration: max_dmso_pct = {current_dmso:.1f}%")
    print(f"Analysis: {total_pairs} unique compound-concentration pairs")
    print(f"  ✓ Feasible with current config: {feasible_count - warning_count}/{total_pairs}")
    if warning_count > 0:
        print(f"  ⚠️  Need config adjustment: {warning_count}/{total_pairs}")
    if error_count > 0:
        print(f"  ❌ Impossible: {error_count}/{total_pairs}")
    
    if issues:
        print("\n" + "-"*90)
        print("ISSUES DETECTED:")
        print("-"*90)
        for issue in issues:
            print(issue)
    
    if error_count > 0:
        print("\n" + "="*90)
        print("RESULT: ❌ CRITICAL - Some concentrations impossible")
        print("="*90)
        print("\nThese concentrations cannot be achieved with ANY configuration.")
        print("Options:")
        print("  1. Use lower target concentrations")
        print("  2. Request higher concentration stocks")
        print("  3. Redesign assay parameters")
        return False
    
    elif warning_count > 0:
        print("\n" + "="*90)
        print("RESULT: ⚠️  CONFIGURATION REQUIRES ADJUSTMENT")
        print("="*90)
        print(f"\nThe following concentrations require DMSO% adjustment:")
        print(f"\n  Current configuration: \"max_dmso_pct\": {current_dmso:.1f}")
        print(f"  Minimum required:    \"max_dmso_pct\": {required_dmso:.2f}\n")
        print(f"RECOMMENDATION: Update config.json")
        print(f'  Change "max_dmso_pct": {current_dmso:.1f} → "max_dmso_pct": {required_dmso:.2f}')
        print(f"\nThen re-run the pipeline.")
        return False
    
    else:
        print("\n" + "="*90)
        print("RESULT: ✅ ALL CONCENTRATIONS FEASIBLE")
        print("="*90)
        print(f"\n✓ All {total_pairs} concentrations achievable")
        print(f"✓ Current DMSO limit ({current_dmso:.1f}%) is sufficient")
        print(f"✓ Pipeline can proceed\n")
        return True


def run_preflight_validation(
    df: pd.DataFrame,
    config: dict,
    highest_stock_mm: float,
) -> bool:
    """
    Execute pre-flight validation workflow.
    
    Args:
        df: DataFrame with compound-concentration pairs (from merge_layout_with_meta)
        config: Configuration dictionary
        highest_stock_mm: Highest stock concentration in mM (extracted from compound metadata)
        
    Returns:
        True if all concentrations are feasible; False otherwise
    """
    
    max_dmso_pct = float(config.get('max_dmso_pct', 0.1))
    working_volume_ul = float(config.get('working_volume_ul', 40))
    sourceplate_type = str(config.get('sourceplate_type', 'S.100 Plate'))
    
    result = validate_all_concentrations(
        df,
        highest_stock_mm,
        working_volume_ul,
        sourceplate_type,
        max_dmso_pct,
    )
    
    return print_preflight_report(result)
