# Tier 3 — Exclusion scenario

Upload these in the iPLAID workbench (Dispenser: iDOT, Source plate: S.100 Plate, leave the Source plate layout field empty so iPLAID designs one from scratch). Expected behavior: 1 compound (`Compound09`) is excluded entirely. A red `is-error` banner names the excluded compound. On the destination plate visualization, the wells planned for that compound show a red diagonal line. The downloaded source-prep `.txt` carries an `EXCLUDED COMPOUNDS` header.

## Why this triggers Tier 3

- `Compound01`..`Compound08` each have 11 distinct target concentrations spanning 11 decades (with `highest_stock_mM=1000`, the stockfinder picks one stock per decade from 1000 down to 1e-7 mM). The from-scratch source-plate algorithm fills source rows A..H with those 8 compounds in Phase A using cols 1–11. Row H has H12 reserved for the DMSO control, so it has 0 trailing free cols; rows A–G each have 1 trailing free col (col 12). Total free: 7 wells.
- `Compound09` has 8 distinct target concentrations → 8 stocks needed. 8 > 7 free wells → Tier 3 exclusion. The compound is dropped from the source plate and its 8 planned target wells are skipped in the protocol; they show up in `excluded_target_wells` on the result.

## Files

- `layout.csv` — target plate wells with compounds + target concentrations
- `meta.csv` — compound metadata (`highest_stock_mM=1000` for all real compounds, plus a `DMSO,0,DMSO` control row)
- `config.json` — iDOT run config matching `config/config.template.json` (working volume 50 µL, max DMSO 0.1%)
