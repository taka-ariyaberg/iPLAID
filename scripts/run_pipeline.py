#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from iplaid.pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]

    parser = argparse.ArgumentParser(
        description="Run the iPLAID pipeline against config/config.json and the repo input files.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=repo_root,
        help="Path to the iPLAID repository root. Defaults to this script's parent repo.",
    )
    parser.add_argument(
        "--skip-source-prep",
        action="store_true",
        help="Skip generation of source plate preparation instructions.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_pipeline(
        project_root=args.project_root,
        include_source_prep=not args.skip_source_prep,
    )


if __name__ == "__main__":
    main()
