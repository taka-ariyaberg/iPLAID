"""
Pre-flight Validation Module

Builds a structured feasibility assessment before the pipeline runs.
The assessment is solvent-aware and can distinguish:
- impossible concentration / stock combinations
- solvent cap settings that are too low
- solvent families that are used without solvent-only wells
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .solvents import clean_label, get_solvent_cap_pct, label_key


class PreflightAssessmentError(ValueError):
    """Raised when the structured pre-flight assessment contains blocking issues."""

    def __init__(self, assessment: dict):
        self.assessment = assessment
        blocking_count = len(assessment.get("blockingIssues", []))
        message = (
            f"Pre-flight assessment found {blocking_count} blocking issue"
            f"{'' if blocking_count == 1 else 's'}."
        )
        super().__init__(message)


def get_min_pipette_volume_nl(sourceplate_type: str) -> float:
    """Get minimum pipette volume for source plate type in nanoliters."""
    return 30.0 if sourceplate_type == "S.200" else 8.0


def calculate_required_solvent_pct(
    target_conc_um: float,
    highest_stock_mm: float,
    working_volume_ul: float,
    sourceplate_type: str,
) -> tuple[bool, float | None, str]:
    """
    Calculate the minimum carrier-solvent percentage needed for a target concentration.

    Tries the full 10-fold dilution series derived from the highest available stock and
    returns the least solvent percentage required to stay within minimum pipette limits.
    """
    if highest_stock_mm == 0:
        return True, 0.0, "Solvent row"
    if target_conc_um == 0:
        return True, 0.0, "Zero target"

    min_pipette_nl = get_min_pipette_volume_nl(sourceplate_type)
    lowest_stock_mM = 0.0000001
    availstocks_mM = [
        highest_stock_mm / (10 ** x)
        for x in range(int(np.ceil(np.log10(highest_stock_mm / lowest_stock_mM))) + 1)
    ]

    min_required_pct = 999.0
    best_stock = None

    for stock_mm in availstocks_mM:
        max_usable_stock = (working_volume_ul * target_conc_um) / min_pipette_nl
        if stock_mm > max_usable_stock:
            continue

        solvent_pct_needed = (target_conc_um * 100) / (stock_mm * 1000)
        if solvent_pct_needed <= 100 and solvent_pct_needed < min_required_pct:
            min_required_pct = solvent_pct_needed
            best_stock = stock_mm

    if best_stock is None:
        return False, None, "No stock in the dilution series can satisfy the pipetting limits."

    return True, min_required_pct, f"Requires at least {min_required_pct:.3f}% carrier solvent"


def _build_solvent_family_rows(df: pd.DataFrame, config: dict) -> list[dict]:
    families: list[dict] = []
    compound_rows = df.loc[~df["is_solvent_control"]].copy()
    if compound_rows.empty:
        return families

    for solvent_key, group in compound_rows.groupby("solvent_key", sort=True):
        solvent_name = clean_label(group["solvent"].iloc[0])
        control_well_count = int(
            df.loc[df["is_solvent_control"] & df["solvent_key"].eq(solvent_key)].shape[0]
        )
        families.append(
            {
                "solvent": solvent_name,
                "solventKey": solvent_key,
                "compoundCount": int(group["cmpdname"].nunique()),
                "compoundWellCount": int(len(group)),
                "controlWellCount": control_well_count,
                "configuredCapPct": float(get_solvent_cap_pct(config, solvent_name)),
                "requiredCapPct": 0.0,
                "status": "ok",
            }
        )

    return families


def assess_preflight_validation(df: pd.DataFrame, config: dict) -> dict:
    """Create a structured solvent-aware pre-flight assessment."""
    working_volume_ul = float(config.get("working_volume_ul", 40))
    sourceplate_type = str(config.get("sourceplate_type", "S.100 Plate"))

    compound_rows = df.loc[~df["is_solvent_control"]].copy()
    solvent_families = _build_solvent_family_rows(df, config)
    family_by_key = {entry["solventKey"]: entry for entry in solvent_families}

    warnings: list[str] = []
    blocking_issues: list[str] = []
    requirements: list[dict] = []
    cap_recommendations: list[dict] = []

    for family in solvent_families:
        if family["compoundWellCount"] > 0 and family["controlWellCount"] == 0:
            family["status"] = "warning"
            warnings.append(
                f'Solvent "{family["solvent"]}" is used by compounds but has no solvent-only wells on the target plate.'
            )

    grouped_pairs = compound_rows.groupby(
        ["cmpdname", "CONCuM", "highest_stock_mM", "solvent", "solvent_key"],
        dropna=False,
    ).size().reset_index(name="count")

    for _, row in grouped_pairs.iterrows():
        compound = clean_label(row["cmpdname"])
        target_conc = float(row["CONCuM"])
        highest_stock_mm = float(row["highest_stock_mM"])
        solvent_name = clean_label(row["solvent"])
        solvent_key = label_key(row["solvent_key"])
        configured_cap_pct = float(get_solvent_cap_pct(config, solvent_name))

        is_feasible, required_pct, reason = calculate_required_solvent_pct(
            target_conc,
            highest_stock_mm,
            working_volume_ul,
            sourceplate_type,
        )

        requirement = {
            "compound": compound,
            "targetConcUm": target_conc,
            "highestStockMm": highest_stock_mm,
            "solvent": solvent_name,
            "configuredCapPct": configured_cap_pct,
            "requiredSolventPct": required_pct,
            "feasible": is_feasible,
            "reason": reason,
            "wellCount": int(row["count"]),
            "status": "ok",
        }

        family_entry = family_by_key.get(solvent_key)
        if family_entry is not None and required_pct is not None:
            family_entry["requiredCapPct"] = max(
                float(family_entry["requiredCapPct"]),
                float(required_pct),
            )

        if not is_feasible:
            requirement["status"] = "error"
            if family_entry is not None:
                family_entry["status"] = "error"
            blocking_issues.append(
                f"{compound} @ {target_conc:.4g} µM ({solvent_name}) is impossible: {reason}"
            )
        elif required_pct is not None and required_pct > configured_cap_pct:
            requirement["status"] = "needs_config"
            if family_entry is not None:
                family_entry["status"] = "error"
            blocking_issues.append(
                f"{compound} @ {target_conc:.4g} µM ({solvent_name}) needs {required_pct:.3f}% solvent "
                f"but the configured cap is {configured_cap_pct:.3f}%."
            )
            cap_recommendations.append(
                {
                    "solvent": solvent_name,
                    "configuredCapPct": configured_cap_pct,
                    "requiredCapPct": float(required_pct),
                }
            )

        requirements.append(requirement)

    deduped_cap_recommendations: dict[str, dict] = {}
    for item in cap_recommendations:
        key = label_key(item["solvent"])
        existing = deduped_cap_recommendations.get(key)
        if existing is None or item["requiredCapPct"] > existing["requiredCapPct"]:
            deduped_cap_recommendations[key] = item
    cap_recommendations = sorted(
        deduped_cap_recommendations.values(),
        key=lambda item: (label_key(item["solvent"]), item["requiredCapPct"]),
    )

    for family in solvent_families:
        if family["status"] == "ok" and family["requiredCapPct"] > family["configuredCapPct"]:
            family["status"] = "error"

    summary = {
        "compoundRowsChecked": int(len(compound_rows)),
        "uniqueCompoundTargets": int(len(grouped_pairs)),
        "solventFamilyCount": int(len(solvent_families)),
        "warningCount": int(len(warnings)),
        "blockingIssueCount": int(len(blocking_issues)),
    }

    return {
        "ok": len(blocking_issues) == 0,
        "summary": summary,
        "warnings": warnings,
        "blockingIssues": blocking_issues,
        "solventFamilies": solvent_families,
        "requirements": requirements,
        "capRecommendations": cap_recommendations,
    }


def print_preflight_report(assessment: dict) -> None:
    """Print a concise CLI-oriented view of the structured assessment."""
    summary = assessment["summary"]
    print("\n" + "=" * 90)
    print("PRE-FLIGHT ASSESSMENT")
    print("=" * 90)
    print(
        f"Checked {summary['uniqueCompoundTargets']} unique compound/concentration targets "
        f"across {summary['solventFamilyCount']} solvent families."
    )

    if assessment["warnings"]:
        print("\nWarnings:")
        for warning in assessment["warnings"]:
            print(f"  • {warning}")

    if assessment["blockingIssues"]:
        print("\nBlocking issues:")
        for issue in assessment["blockingIssues"]:
            print(f"  • {issue}")

    if assessment["capRecommendations"]:
        print("\nCap recommendations:")
        for item in assessment["capRecommendations"]:
            print(
                f"  • {item['solvent']}: raise solvent cap from "
                f"{item['configuredCapPct']:.3f}% to at least {item['requiredCapPct']:.3f}%"
            )

    if assessment["ok"]:
        print("\nResult: pipeline can proceed.")
    else:
        print("\nResult: resolve blocking issues before running the pipeline.")


def run_preflight_validation(df: pd.DataFrame, config: dict) -> dict:
    """Build and print the structured pre-flight assessment."""
    assessment = assess_preflight_validation(df, config)
    print_preflight_report(assessment)
    return assessment
