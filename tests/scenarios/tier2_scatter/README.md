# Tier 2 — Scatter scenario

Upload these in the iPLAID workbench (Dispenser: iDOT, Source plate: S.100 Plate, leave the Source plate layout field empty so iPLAID designs one from scratch). Expected behavior: 1 compound (`Compound09`) gets scattered into non-contiguous source-plate wells. A yellow `is-warning` banner appears on the results page naming the scattered compound.

## Why this triggers Tier 2

- `Compound01`..`Compound08` each have 9 distinct target concentrations spanning 9 decades, so the stockfinder assigns 9 distinct source stocks per compound. The from-scratch source-plate algorithm fills source rows A..H with those 8 compounds in Phase A (cols 1–9 in each row), leaving cols 10–12 free (row H also has H12 reserved for the DMSO control, so row H ends with only 2 trailing free cols).
- `Compound09` has 4 distinct target concentrations → 4 stocks needed. No row has 4 contiguous free cols (max is 3), but the plate still has 23 free wells overall → Tier 2 scatter kicks in. The compound's 4 stocks land in `A10`, `A11`, `A12`, `B10`.

## Files

- `layout.csv` — target plate wells with compounds + target concentrations
- `meta.csv` — compound metadata (`highest_stock_mM=100` for all real compounds, plus a `DMSO,0,DMSO` control row)
- `config.json` — iDOT run config matching `config/config.template.json` (working volume 50 µL, max DMSO 0.1%)
