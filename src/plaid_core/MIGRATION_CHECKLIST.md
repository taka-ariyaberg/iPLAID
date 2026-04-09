# PLAID_Core Migration Checklist

Historical internal note.

This file originally tracked the migration of PLAID_Core into iPLAID. That migration has already been completed in this repository.

## For current users

- Do not copy `PLAID_Core` into this repo manually.
- Do not install from `src/iplaid/plaid_core`.
- Install the repository from the root with `pip install -e .`.
- Use the root [README.md](/Users/takar834/Documents/UU/TIMED/Tools/iPLAID/README.md) for setup and operation.

## For maintainers

If PLAID_Core is ever extracted again or re-integrated into a different repository, create a fresh migration plan instead of following the old migration steps that used to live here.
