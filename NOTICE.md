# Third-Party Notices

iPLAID bundles and builds upon third-party software. This file lists each upstream project, its license, and where its license text lives in this repository.

## PLAID — Plate Layouts using Artificial Intelligence Design

- **Upstream repository:** https://github.com/pharmbio/plaid
- **Authors:** Maria Andreina Francisco Rodríguez, Ola Spjuth, and the pharmbio group at Uppsala University
- **License:** Apache License 2.0 — see [`LICENSES/Apache-2.0.txt`](LICENSES/Apache-2.0.txt)
- **Use in iPLAID:** the contents of [`src/plaid_core/`](src/plaid_core/) are derived from PLAID. The MiniZinc model, the constraint-programming design logic, and the Python wrappers around the solver originate from this upstream. iPLAID adapts and bundles them as the *Design with PLAID* layout-design engine that feeds the iPLAID dispense pipeline.

The directory `src/plaid_core/` and any modifications to its files therefore remain governed by the Apache License 2.0. Anything outside `src/plaid_core/` is original iPLAID code and is governed by the terms in the project [`LICENSE.md`](LICENSE.md).

### Citation

If your work uses iPLAID's design step (or PLAID directly), please cite the original paper:

```bibtex
@article{PLAID2023,
  author  = {Francisco Rodr{\'\i}guez, Mar{\'\i}a Andre{\'\i}na and Carreras Puigvert, Jordi and Spjuth, Ola},
  title   = {Designing Microplate Layouts Using Artificial Intelligence},
  journal = {Artificial Intelligence in the Life Sciences},
  volume  = {3},
  year    = {2023},
  doi     = {10.1016/j.ailsci.2023.100073}
}
```

### Disclaimer carried from upstream

> The PLAID team accepts no responsibility or liability for the use of PLAID or any direct or indirect damages arising out of its use.

---

## MiniZinc + Gecode

- **MiniZinc** is distributed under the Mozilla Public License 2.0 (https://github.com/MiniZinc/libminizinc).
- **Gecode** is distributed under the MIT License (https://github.com/Gecode/gecode).

Both are built from upstream sources at image-build time inside the iPLAID Dockerfile. They are not copied into the iPLAID source tree; their licenses live in their own repositories and inside the produced container image at `/opt/minizinc/` and `/opt/gecode/` respectively.

---

## How to update this file

When a new upstream dependency is bundled into the iPLAID source tree (i.e. its source is copied into this repository, not just installed by `pip` or built in Docker), add a new section here describing it, place its license under [`LICENSES/`](LICENSES/), and link both from this NOTICE.
