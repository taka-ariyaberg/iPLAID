"""
Calculations Module

Consolidates all mathematical calculations:
- Stock concentration selection based on DMSO constraints
- Volume calculations from stock concentrations
- Well name formatting utilities
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.iplaid.solvents import clean_label, get_solvent_cap_pct


# Stock finding utilities
def stockfinder_safe(
    stockfinder_fn,
    *,
    concUM: float,
    highest_stock_mM: float,
    V2_ul: float,
    dmso_percmax: float,
    sourceplate_type: str,
) -> float:
    """
    Wrapper around stockfinder() that explicitly passes sourceplate_type.

    Args:
        stockfinder_fn: The stockfinder function to call
        concUM: Target concentration in µM
        highest_stock_mM: Highest available stock concentration in mM
        V2_ul: Target well volume in µL
        dmso_percmax: Maximum carrier-solvent percentage allowed
        sourceplate_type: Source plate type (e.g. "S.100 Plate", "S.200")
        
    Returns:
        Optimal stock concentration in mM
    """
    return stockfinder_fn(concUM, highest_stock_mM, V2_ul, dmso_percmax, sourceplate_type)


def remove_leading_zero(well_name: str) -> str:
    """
    Remove leading zero from well name (e.g. A08 → A8, B12 → B12).
    
    Args:
        well_name: Well name like "A08"
        
    Returns:
        Formatted well name
    """
    return well_name[0] + well_name[1:3].lstrip("0")


def volume_from_stock(concUM: float, stock_conc_mM: float, working_volume_ul: float) -> float:
    """
    Calculate volume of stock needed for target concentration.
    
    Args:
        concUM: Target concentration in µM
        stock_conc_mM: Stock concentration in mM
        working_volume_ul: Working volume of target well in µL
        
    Returns:
        Stock volume needed in µL
    """
    concUM = (concUM * working_volume_ul) / stock_conc_mM if stock_conc_mM != 0 else 0
    return concUM / 1000


def stockfinder(
    concUM: float,
    highest_stock_mM: float,
    V2_ul: float,
    dmso_percmax: float,
    sourceplate_type: str,
) -> float:
    """
    Find optimal stock concentration that respects solvent percentage constraints.
    
    Generates a dilution series from the highest stock and selects the concentration
    that allows the requested target concentration to be achieved while respecting
    the minimum pipette volume and maximum DMSO percentage constraints.
    
    Args:
        concUM: Target concentration in µM
        highest_stock_mM: Highest available stock concentration in mM
        V2_ul: Target well volume in µL
        dmso_percmax: Maximum carrier-solvent percentage allowed
        sourceplate_type: Source plate type (e.g. "S.100 Plate", "S.200")
        
    Returns:
        Optimal stock concentration in mM
        
    Raises:
        Exception: If no suitable stock concentration found
    """
    if highest_stock_mM != 0:
        lowest_stock_mM = 0.0000001
        availstocks_mM = [
            highest_stock_mM / (10 ** x)
            for x in range(int(np.ceil(np.log10(highest_stock_mM / lowest_stock_mM))) + 1)
        ]

        MinV1_nl = 30 if sourceplate_type == "S.200" else 8

        MaxV1_nl = (dmso_percmax / 100) * (V2_ul * 1000)

        C1_low = (V2_ul * concUM) / MaxV1_nl
        C1_high = (V2_ul * concUM) / MinV1_nl

        psblstocks = [x for x in availstocks_mM if x >= C1_low and x <= C1_high]

        if psblstocks:
            highestStock = max(psblstocks)
            return highestStock
        else:
            # Build diagnostic error message
            diagnostics = []
            diagnostics.append(f"Target: {concUM:.4g} µM")
            diagnostics.append(f"Well volume: {V2_ul} µL")
            diagnostics.append(f"Solvent limit: {dmso_percmax:.1f}% = {MaxV1_nl:.0f} nL")
            diagnostics.append(f"Highest available stock: {highest_stock_mM:.2f} mM")
            diagnostics.append(f"Required stock range: {C1_low:.2f}–{C1_high:.2f} mM")
            
            if highest_stock_mM < C1_low:
                min_required_dmso = 100 * (V2_ul * concUM) / (highest_stock_mM * V2_ul * 1000)
                diagnostics.append(
                    f"\nREASON: Stock too LOW\n"
                    f"  Available: {highest_stock_mM:.2f} mM\n"
                    f"  Need minimum: {C1_low:.2f} mM\n"
                    f"  Shortfall: {(C1_low/highest_stock_mM - 1)*100:.0f}%\n"
                    f"\nTO FIX:\n"
                    f"  • Increase the solvent cap from {dmso_percmax:.1f}% to >= {min_required_dmso:.2f}%\n"
                    f"  • OR use higher concentration stock (>= {C1_low:.2f} mM)\n"
                    f"  • OR target lower concentration"
                )
            elif highest_stock_mM > C1_high:
                min_required_dmso = 100 * (V2_ul * concUM) / (highest_stock_mM * V2_ul * 1000)
                diagnostics.append(
                    f"\nREASON: Stock too HIGH and minimum pipette volume constraint\n"
                    f"  Available: {highest_stock_mM:.2f} mM is above required max\n"
                    f"  Maximum allowed: {C1_high:.2f} mM\n"
                    f"  Would require volume: <{MinV1_nl} nL (below {sourceplate_type} limit)\n"
                    f"\nTO FIX:\n"
                    f"  • Increase the solvent cap from {dmso_percmax:.1f}% to >= {min_required_dmso:.2f}%\n"
                    f"  • OR use lower concentration stock\n"
                    f"  • OR target higher concentration"
                )
            
            raise Exception("\n".join(diagnostics))
    else:
        return 0


# Stock selection
def assign_stock_concentrations(
    df: pd.DataFrame,
    *,
    stockfinder_fn,
    stockfinder_safe_fn,
    working_volume_ul: float,
    config: dict,
    sourceplate_type: str,
) -> pd.DataFrame:
    """
    Assign optimal stock concentrations to each row based on solvent constraints.
    
    Args:
        df: DataFrame with CONCuM and highest_stock_mM columns
        stockfinder_fn: Function that finds optimal stock
        stockfinder_safe_fn: Wrapper that sets plate type context
        working_volume_ul: Target well working volume
        config: Full run configuration used to resolve solvent caps
        sourceplate_type: Source plate type
        
    Returns:
        DataFrame with new stock_conc_mM column
        
    Raises:
        ValueError: If stock selection fails for any row
    """
    df = df.copy()
    
    # Determine minimum pipette volume based on plate type
    min_pipette_nl = 30 if sourceplate_type == "S.200" else 8
    # Track failures for diagnostic reporting
    failed_rows = []

    def find_stock_with_diagnostics(row):
        """Find stock with detailed error tracking."""
        solvent_name = clean_label(row.get("solvent", "DMSO"))
        solvent_cap_pct = float(get_solvent_cap_pct(config, solvent_name))
        max_solvent_nl = (solvent_cap_pct / 100) * (working_volume_ul * 1000)

        try:
            stock = stockfinder_safe_fn(
                stockfinder_fn,
                concUM=row["CONCuM"],
                highest_stock_mM=row["highest_stock_mM"],
                V2_ul=working_volume_ul,
                dmso_percmax=solvent_cap_pct,
                sourceplate_type=sourceplate_type,
            )
            return stock
        except Exception as e:
            # Calculate what ranges would be needed
            conc_um = row["CONCuM"]
            highest_stock = row["highest_stock_mM"]
            C1_low = (working_volume_ul * conc_um) / max_solvent_nl
            C1_high = (working_volume_ul * conc_um) / min_pipette_nl
            
            failed_rows.append({
                "well": row.get("well", "UNKNOWN"),
                "compound": row.get("cmpdname", "UNKNOWN"),
                "solvent": solvent_name,
                "target_conc_um": conc_um,
                "highest_stock_mm": highest_stock,
                "required_range_mm": (C1_low, C1_high),
                "solvent_cap_pct": solvent_cap_pct,
                "max_solvent_nl": max_solvent_nl,
                "error": str(e),
            })
            return np.nan

    stock_conc_series = df.apply(find_stock_with_diagnostics, axis=1)
    
    # Convert to Series if needed (handles empty DataFrame edge case)
    if isinstance(stock_conc_series, pd.DataFrame):
        stock_conc_series = stock_conc_series.iloc[:, 0] if stock_conc_series.shape[1] > 0 else pd.Series(dtype=float)
    
    df["stock_conc_mM"] = stock_conc_series

    # Report failures with diagnostic information
    if failed_rows:
        print("\n" + "="*90)
        print("⚠️  STOCK CONCENTRATION ASSIGNMENT FAILURES")
        print("="*90)
        
        # Group failures by compound and concentration
        failure_summary = {}
        for fail in failed_rows:
            key = (fail["compound"], fail["target_conc_um"])
            if key not in failure_summary:
                failure_summary[key] = {"wells": [], "info": fail}
            failure_summary[key]["wells"].append(fail["well"])
        
        print("\nFailed concentration assignments:")
        print("-" * 90)
        for (compound, target_conc), data in sorted(failure_summary.items()):
            fail_info = data["info"]
            wells = data["wells"]
            print(f"\n  • {compound} @ {target_conc:.4g} µM  ({len(wells)} wells: {', '.join(sorted(wells))})")
            print(f"    ├─ Available stock: {fail_info['highest_stock_mm']:.2f} mM")
            print(f"    ├─ Required stock range: {fail_info['required_range_mm'][0]:.2f} – {fail_info['required_range_mm'][1]:.2f} mM")
            print(
                f"    ├─ Solvent: {fail_info['solvent']}"
            )
            print(
                f"    ├─ Solvent limit: {fail_info['solvent_cap_pct']:.1f}% = "
                f"{fail_info['max_solvent_nl']:.0f} nL per {working_volume_ul} µL well"
            )
            
            # Provide diagnostic insight
            c_low, c_high = fail_info["required_range_mm"]
            highest = fail_info["highest_stock_mm"]
            
            if highest < c_low:
                print(f"    └─ REASON: Available stock ({highest:.2f} mM) is too LOW")
                print(
                    f"              Need minimum {c_low:.2f} mM to achieve {target_conc:.4g} µM "
                    f"with only {fail_info['solvent_cap_pct']:.1f}% solvent"
                )
                print("              SUGGESTION: Increase the solvent cap or use higher concentration stock")
            elif highest < c_high:
                print(f"    └─ REASON: Available stock ({highest:.2f} mM) is below optimal range ({c_high:.2f} mM)")
                print(f"              Would require >0.5% pipette volume error")
                print("              SUGGESTION: Increase the solvent cap to allow higher dispense volumes")
            else:
                print("    └─ REASON: No suitable stock in range (check solvent-cap calculation)")
        
        print("\n" + "="*90)
        raise ValueError(
            f"Stock selection failed for {len(failed_rows)} rows across {len(failure_summary)} "
            f"unique compound-concentration combinations. See diagnostic report above."
        )

    return df


def make_stock_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create summary of stock concentrations used.
    
    Args:
        df: DataFrame with cmpdname and stock_conc_mM columns
        
    Returns:
        Summary DataFrame with count of each stock concentration per compound
    """
    return (
        df[["cmpdname", "stock_conc_mM"]]
        .value_counts()
        .to_frame("count")
        .reset_index()
    )
