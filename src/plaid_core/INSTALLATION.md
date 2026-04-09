# PLAID_Core Installation

This file documents the solver-specific setup for the bundled `plaid_core` package.

If you are setting up the full iPLAID repository, use the root [README.md](/Users/takar834/Documents/UU/TIMED/Tools/iPLAID/README.md) as the primary guide.

## In this repository

`plaid_core` is already included under `src/plaid_core/`. Install from the repo root:

```bash
pip install -e /path/to/iPLAID
```

You do not need a separate clone or copy step.

## Python requirement

- Python 3.11+

## MiniZinc requirement

MiniZinc is required for solving layouts.

### macOS

```bash
brew install minizinc
```

or install from `https://www.minizinc.org/`.

### Ubuntu / Debian

```bash
sudo apt-get install minizinc
```

### Windows

Install from `https://www.minizinc.org/`.

## Verification

```bash
python -c "import plaid_core; print('plaid_core import OK')"
minizinc --version
minizinc --solvers
```

`minizinc --solvers` should list an available solver such as Gecode.

## macOS PATH note

If MiniZinc is installed through the app bundle and not on your shell `PATH`, the code also checks:

```text
/Applications/MiniZincIDE.app/Contents/Resources/minizinc
```

If needed, add it manually:

```bash
export PATH="/Applications/MiniZincIDE.app/Contents/Resources:$PATH"
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `minizinc: command not found` | Install MiniZinc and verify it is on `PATH` |
| `MiniZinc not found` from Python | Verify `minizinc --version`; on macOS, check the app-bundle path |
| `Gecode solver not found` | Reinstall MiniZinc with bundled solvers or choose another available solver |
| `ModuleNotFoundError: plaid_core` | Reinstall from repo root with `pip install -e .` |

## Historical note

Older docs in this folder may refer to copying `PLAID_Core` into another project. That was part of an earlier integration workflow and is not the recommended setup for this repository.
