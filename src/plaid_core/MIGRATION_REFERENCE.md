# PLAID_Core Migration Reference

Historical internal reference.

The original contents of this file documented how PLAID_Core was copied into iPLAID during an earlier integration phase. That workflow is no longer the active setup model for this repository.

## Current truth

- `plaid_core` is already present under `src/plaid_core/`.
- The repository installs both `iplaid` and `plaid_core` through the root `pyproject.toml`.
- The recommended installation command is `pip install -e .` from the repo root.

For current usage instructions, see:

- [README.md](/Users/takar834/Documents/UU/TIMED/Tools/iPLAID/README.md)
- [src/plaid_core/README.md](/Users/takar834/Documents/UU/TIMED/Tools/iPLAID/src/plaid_core/README.md)
