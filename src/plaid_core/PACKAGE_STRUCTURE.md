# PLAID_Core Package Structure

This is a quick map of the bundled `plaid_core` package inside iPLAID.

## Directory map

```text
src/plaid_core/
├── __init__.py
├── config.py
├── designer.py
├── exceptions.py
├── output.py
├── solver.py
├── validators.py
├── templates/
│   ├── layout_predicates.mzn
│   └── plate-design.mzn
├── examples/
│   ├── advanced_usage.py
│   ├── basic_usage.py
│   └── config_examples.json
└── *.md
```

## Core modules

| File | Purpose |
|------|---------|
| `config.py` | `PlateConfig`, `Compound`, and `Control` definitions |
| `designer.py` | `PlateDesigner` public entrypoint |
| `solver.py` | MiniZinc solver wrapper |
| `output.py` | Layout parsing and export helpers |
| `validators.py` | Config and MiniZinc availability checks |
| `exceptions.py` | PLAID_Core exception types |

## Templates

| File | Purpose |
|------|---------|
| `templates/plate-design.mzn` | Main MiniZinc model |
| `templates/layout_predicates.mzn` | Helper predicates used by the model |

## Examples

| File | Purpose |
|------|---------|
| `examples/basic_usage.py` | Minimal direct Python usage |
| `examples/advanced_usage.py` | More complex design configuration |
| `examples/config_examples.json` | Example serialized configs |

## Usage note

This package is already bundled into the repository. For setup and operation of the full project, use the root [README.md](/Users/takar834/Documents/UU/TIMED/Tools/iPLAID/README.md).
