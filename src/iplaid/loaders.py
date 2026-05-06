from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

from .solvents import clean_label, label_key
from .wells import canonical_well_name


def load_layout_csv(layout_path):
    layout_path = Path(layout_path)
    df = pd.read_csv(layout_path)
    
    # Reset index if it was created from a column
    if 'index' in df.columns or (df.index.name and 'Unnamed' not in str(df.index.name)):
        df = df.reset_index(drop=True)
    
    # Fix column misalignment: the plateid got consumed, so columns are shifted
    # Check if the 'plateID' column actually contains well names (like D05, D06)
    if 'plateID' in df.columns and 'well' in df.columns:
        try:
            # Check if plateID column looks like well names
            plateID_vals = df['plateID'].astype(str).str.strip()
            if any(str(val)[0].isalpha() and str(val)[1].isdigit() for val in plateID_vals.head()):
                # Yes, columns are shifted. Remap them:
                # Current: [plateID, well, cmpdname, CONCuM, cmpdnum]
                # Actually contains: [well, cmpdname, CONCuM, cmpdnum, extra]
                # So: plateID→well, well→cmpdname, cmpdname→CONCuM, CONCuM→cmpdnum, cmpdnum→extra
                
                # Extract the original plateID if it exists in the data (first column typically contains it)
                # If not present, use first plate from the xlsx sheet name or default to "plate_1"
                plate_id_extracted = df.columns[0] if isinstance(df.columns[0], str) else None
                if not plate_id_extracted or plate_id_extracted in ['plateID', 'well', 'cmpdname']:
                    plate_id_extracted = 'plate_1'  # Default only if we can't determine it
                
                df_fixed = pd.DataFrame({
                    'plateID': plate_id_extracted,
                    'well': df['plateID'],
                    'cmpdname': df['well'],
                    'CONCuM': df['cmpdname'],
                    'cmpdnum': df['CONCuM']
                })
                df = df_fixed[['plateID', 'well', 'cmpdname', 'CONCuM']]
        except Exception as e:
            # Log the issue but don't fail - let downstream validation catch it
            import warnings
            warnings.warn(f"Could not auto-fix column misalignment: {e}. Proceeding with data as-is.")
    
    return df


def normalize_layout_df(df):
    df = df.copy()

    required_cols = {"plateID", "well", "cmpdname", "CONCuM"}
    missing_cols = sorted(required_cols - set(df.columns))
    if missing_cols:
        raise ValueError(f"Layout file is missing required columns: {missing_cols}")

    df["cmpdname"] = (
        df["cmpdname"]
        .map(clean_label)
        .replace({"Dimethyl sulfoxide": "DMSO"})
    )
    df["cmpdname_key"] = df["cmpdname"].map(label_key)
    df["well"] = df["well"].astype(str).str.strip().map(canonical_well_name)
    df["plateID"] = df["plateID"].astype(str).str.strip()

    df["CONCuM"] = (
        df["CONCuM"]
        .astype(str)
        .str.replace('"', "", regex=False)
        .str.strip()
        .replace({"nan": np.nan, "": np.nan, "None": np.nan})
    )
    df["CONCuM"] = pd.to_numeric(df["CONCuM"], errors="coerce")

    treatment_type = (
        df["treatment_type"].astype(str)
        if "treatment_type" in df.columns
        else pd.Series("", index=df.index)
    )

    is_named_dmso_control = (
        df["cmpdname_key"].eq("dmso")
        | treatment_type.str.upper().str.contains("DMSO", na=False)
    )
    df.loc[is_named_dmso_control, "CONCuM"] = df.loc[is_named_dmso_control, "CONCuM"].fillna(0)

    df = df.dropna(subset=["well", "CONCuM"]).copy()

    duplicate_wells = df.loc[
        df.duplicated(subset=["plateID", "well"], keep=False),
        ["plateID", "well"],
    ].drop_duplicates()
    if len(duplicate_wells) > 0:
        duplicates = [
            f'{row.plateID} / {row.well}'
            for row in duplicate_wells.itertuples(index=False)
        ]
        raise ValueError(
            "Layout contains duplicate target wells after normalizing well IDs:\n  - "
            + "\n  - ".join(duplicates)
        )

    return df, is_named_dmso_control


def load_meta_csv(meta_path):
    meta_path = Path(meta_path)
    return pd.read_csv(meta_path)


def normalize_meta_df(cmpd_info):
    cmpd_info = cmpd_info.copy()

    meta_required = {"cmpdname", "highest_stock_mM", "solvent"}
    meta_missing = sorted(meta_required - set(cmpd_info.columns))
    if meta_missing:
        raise ValueError(f"Meta file is missing required columns: {meta_missing}")

    cmpd_info["cmpdname"] = cmpd_info["cmpdname"].map(clean_label)
    cmpd_info["solvent"] = cmpd_info["solvent"].map(clean_label)
    cmpd_info["highest_stock_mM"] = pd.to_numeric(
        cmpd_info["highest_stock_mM"], errors="raise"
    )

    blank_names = cmpd_info.loc[cmpd_info["cmpdname"].eq(""), "cmpdname"]
    blank_solvents = cmpd_info.loc[cmpd_info["solvent"].eq(""), "solvent"]
    if len(blank_names) > 0 or len(blank_solvents) > 0:
        raise ValueError("Metadata rows must include both cmpdname and solvent.")

    cmpd_info["cmpdname_key"] = cmpd_info["cmpdname"].map(label_key)
    cmpd_info["solvent_key"] = cmpd_info["solvent"].map(label_key)

    duplicate_names = sorted(
        cmpd_info.loc[
            cmpd_info["cmpdname_key"].duplicated(keep=False),
            "cmpdname",
        ].drop_duplicates().tolist()
    )
    if duplicate_names:
        raise ValueError(
            "Metadata contains duplicate compound names:\n  - " + "\n  - ".join(duplicate_names)
        )

    cmpd_info["is_solvent_control"] = cmpd_info["cmpdname_key"].eq(cmpd_info["solvent_key"])

    invalid_solvent_rows = cmpd_info.loc[
        cmpd_info["is_solvent_control"] & (cmpd_info["highest_stock_mM"] != 0),
        ["cmpdname", "highest_stock_mM"],
    ]
    if len(invalid_solvent_rows) > 0:
        lines = [
            f"{row.cmpdname} has highest_stock_mM={float(row.highest_stock_mM):g}"
            for row in invalid_solvent_rows.itertuples(index=False)
        ]
        raise ValueError(
            "Solvent metadata rows must use highest_stock_mM = 0:\n  - "
            + "\n  - ".join(lines)
        )

    invalid_compounds = cmpd_info.loc[
        ~cmpd_info["is_solvent_control"] & (cmpd_info["highest_stock_mM"] <= 0),
        ["cmpdname", "highest_stock_mM"],
    ]
    if len(invalid_compounds) > 0:
        lines = [
            f"{row.cmpdname} has highest_stock_mM={float(row.highest_stock_mM):g}"
            for row in invalid_compounds.itertuples(index=False)
        ]
        raise ValueError(
            "Compound metadata rows must use highest_stock_mM > 0:\n  - "
            + "\n  - ".join(lines)
        )

    cmpd_info.loc[cmpd_info["is_solvent_control"], "highest_stock_mM"] = 0.0

    control_name_map = (
        cmpd_info.loc[cmpd_info["is_solvent_control"], ["solvent_key", "cmpdname"]]
        .drop_duplicates(subset=["solvent_key"])
        .set_index("solvent_key")["cmpdname"]
        .to_dict()
    )
    cmpd_info["solvent"] = cmpd_info["solvent_key"].map(control_name_map).fillna(cmpd_info["solvent"])

    missing_solvent_controls = sorted(
        {
            row.solvent
            for row in cmpd_info.loc[~cmpd_info["is_solvent_control"], ["solvent", "solvent_key"]].itertuples(index=False)
            if row.solvent_key not in control_name_map
        }
    )
    if missing_solvent_controls:
        raise ValueError(
            "Metadata is missing solvent rows for:\n  - "
            + "\n  - ".join(missing_solvent_controls)
        )

    return cmpd_info


def derive_meta_from_source_layout(layout_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a meta-equivalent DataFrame from a new-shape source plate layout.

    Input columns: cmpdname, conc_mM, solvent, source_plate, source_well.
    Output columns: cmpdname, highest_stock_mM, solvent (one row per compound).

    `highest_stock_mM` is max(conc_mM) over the compound's rows. Solvent must
    be consistent per compound.

    The result is suitable for `normalize_meta_df`, which performs the rest of
    the validation (solvent-control rules, missing-solvent-row check, etc.).
    """
    required = {"cmpdname", "conc_mM", "solvent", "source_plate", "source_well"}
    missing = sorted(required - set(layout_df.columns))
    if missing:
        raise ValueError(f"Source plate layout is missing required columns: {missing}")

    df = layout_df.copy()
    df["cmpdname"] = df["cmpdname"].map(clean_label)
    df["solvent"] = df["solvent"].map(clean_label)

    blank_names = df.loc[df["cmpdname"].eq(""), "cmpdname"]
    blank_solvents = df.loc[df["solvent"].eq(""), "solvent"]
    if len(blank_names) > 0:
        raise ValueError("Source plate layout has blank cmpdname value(s).")
    if len(blank_solvents) > 0:
        raise ValueError("Source plate layout has blank solvent value(s).")

    df["conc_mM"] = pd.to_numeric(df["conc_mM"], errors="raise")

    # Single-pass groupby: aggregate + inconsistency flag in one shot.
    df["cmpdname_key"] = df["cmpdname"].map(label_key)
    grouped = df.groupby("cmpdname_key", as_index=False).agg(
        cmpdname=("cmpdname", "first"),
        highest_stock_mM=("conc_mM", "max"),
        solvent=("solvent", "first"),
        _solvent_nunique=("solvent", "nunique"),
    )

    bad = grouped[grouped["_solvent_nunique"] > 1]
    if not bad.empty:
        lines = []
        for row in bad.itertuples(index=False):
            unique_solvents = sorted(
                df.loc[df["cmpdname_key"].eq(label_key(row.cmpdname)), "solvent"].unique().tolist()
            )
            lines.append(
                f"Inconsistent solvent for cmpdname '{row.cmpdname}': "
                + " vs ".join(repr(s) for s in unique_solvents)
            )
        raise ValueError("\n  - ".join(["Source plate layout has solvent inconsistencies:"] + lines))

    return grouped[["cmpdname", "highest_stock_mM", "solvent"]]


def _format_conc(value: float) -> str:
    """Match Python's default float→str formatting for conc_mM in Liquid Name.

    This must agree with the format produced by the rest of the pipeline when
    constructing Liquid Name internally (so set-equality matching in
    `validate_source_layout_geometry` succeeds). Today the codebase relies on
    plain str(float) — we keep that.
    """
    return str(float(value))


def source_layout_to_legacy_shape(layout_df: pd.DataFrame) -> pd.DataFrame:
    """Rewrite a new-shape source plate layout into the old 3-column shape.

    Output columns: Liquid Name (= `[cmpdname][conc_mM]`), Source Plate,
    Source Well. Downstream consumers (`output.py`,
    `source_plate_prep.py`) read the old shape and remain untouched.
    """
    required = {"cmpdname", "conc_mM", "solvent", "source_plate", "source_well"}
    missing = sorted(required - set(layout_df.columns))
    if missing:
        raise ValueError(f"Source plate layout is missing required columns: {missing}")

    df = layout_df.copy()
    df["cmpdname"] = df["cmpdname"].map(clean_label)
    df["conc_mM"] = pd.to_numeric(df["conc_mM"], errors="raise")
    out = pd.DataFrame({
        "Liquid Name": [
            f"[{name}][{_format_conc(conc)}]"
            for name, conc in zip(df["cmpdname"], df["conc_mM"])
        ],
        "Source Plate": df["source_plate"].astype(str).str.strip().values,
        "Source Well": df["source_well"].astype(str).str.strip().values,
    })
    return out


def merge_layout_with_meta(df, cmpd_info):
    df = df.copy()
    cmpd_info = cmpd_info.copy()

    df["cmpdname_key"] = df["cmpdname"].map(label_key)

    merged = df.merge(
        cmpd_info,
        on="cmpdname_key",
        how="left",
        indicator=True,
        suffixes=("_layout", ""),
    )

    missing_cmpds = merged.loc[merged["_merge"] != "both", "cmpdname_layout"].drop_duplicates().tolist()
    if missing_cmpds:
        raise ValueError(
            "These compounds are missing from metadata:\n  - " + "\n  - ".join(missing_cmpds)
        )

    merged["cmpdname"] = merged["cmpdname"].fillna(merged["cmpdname_layout"])
    merged["solvent"] = merged["solvent"].map(clean_label)
    merged["solvent_key"] = merged["solvent"].map(label_key)
    merged["is_solvent_control"] = (
        merged["is_solvent_control"].fillna(False).astype(bool)
    )

    merged = merged.drop(
        columns=["_merge", "cmpdname_layout"],
        errors="ignore",
    ).copy()
    return merged
