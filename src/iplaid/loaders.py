from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd


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
        .astype(str)
        .str.strip()
        .replace({"Dimethyl sulfoxide": "DMSO"})
    )
    df["well"] = df["well"].astype(str).str.strip()
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

    is_dmso_control = (
        df["cmpdname"].str.lower().eq("dmso")
        | treatment_type.str.upper().str.contains("DMSO", na=False)
    )
    df.loc[is_dmso_control, "CONCuM"] = df.loc[is_dmso_control, "CONCuM"].fillna(0)

    df = df.dropna(subset=["well", "CONCuM"]).copy()
    return df, is_dmso_control


def load_meta_csv(meta_path):
    meta_path = Path(meta_path)
    return pd.read_csv(meta_path)


def normalize_meta_df(cmpd_info):
    cmpd_info = cmpd_info.copy()

    meta_required = {"cmpdname", "highest_stock_mM", "solvent"}
    meta_missing = sorted(meta_required - set(cmpd_info.columns))
    if meta_missing:
        raise ValueError(f"Meta file is missing required columns: {meta_missing}")

    cmpd_info["cmpdname"] = cmpd_info["cmpdname"].astype(str).str.strip()
    cmpd_info["highest_stock_mM"] = pd.to_numeric(
        cmpd_info["highest_stock_mM"], errors="raise"
    )

    return cmpd_info


def merge_layout_with_meta(df, cmpd_info):
    df = df.copy()
    cmpd_info = cmpd_info.copy()

    merged = df.merge(cmpd_info, on="cmpdname", how="left", indicator=True)

    missing_cmpds = merged.loc[merged["_merge"] != "both", "cmpdname"].drop_duplicates().tolist()
    if missing_cmpds:
        raise ValueError(
            "These compounds are missing from metadata:\n  - " + "\n  - ".join(missing_cmpds)
        )

    merged = merged.drop(columns=["_merge"]).copy()
    return merged
