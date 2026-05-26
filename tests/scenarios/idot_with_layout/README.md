# iDOT with user-supplied source-plate layout

Mirror of `echo_with_layout/` but for iDOT. Demonstrates the `existing_layout`
upload path on the iDOT dispenser: the user provides a `source_layout.csv`
that hand-places each liquid into specific wells, bypassing the pipette-friendly
auto-assignment algorithm.

The wells in `source_layout.csv` are deliberately placed in a non-default
pattern (compounds on the right side of the plate, DMSO at A12) so a glance
at the produced protocol confirms the upload is being honored — the new
algorithm would have placed compounds at A1-D2 and DMSO at H12.

Upload all three CSVs (`layout.csv`, `meta.csv`, `source_layout.csv`) plus the
config in the iPLAID workbench. Expected behavior: protocol uses the wells
from `source_layout.csv` verbatim; no warning banners; no scatter / exclusion.
