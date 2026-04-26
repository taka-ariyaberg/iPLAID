"""
I/O and Configuration Module

Consolidates all project initialization and configuration:
- Configuration file loading and validation
- Project root discovery 
- Path resolution for all input/output files
- Plate specification loading
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

from .download_filenames import build_run_artifact_paths


# Configuration loading
REQUIRED_CONFIG_KEYS = [
    "layout_file",
    "meta_file",
    "user_name",
    "protocol_name",
    "sourceplate_type",
    "target_plate_type",
    "working_volume_ul",
    "max_dmso_pct",
    "source_prep_overage_pct",
    "min_pipette_volume_uL",
    "dilution_solvent",
    "source_well_fill_pct",
    "standard_prep_volume_uL",
    "output_timestamp_format",
]


def validate_config_dict(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate an in-memory configuration dictionary.

    Args:
        cfg: Configuration dictionary

    Returns:
        The validated configuration dictionary

    Raises:
        KeyError: If required config keys are missing
    """
    missing = [k for k in REQUIRED_CONFIG_KEYS if k not in cfg]
    if missing:
        raise KeyError(f"Missing required config keys: {missing}")
    return cfg


def load_config(config_path: Path) -> Dict[str, Any]:
    """
    Load and validate project configuration from JSON file.
    
    Args:
        config_path: Path to config.json
        
    Returns:
        Configuration dictionary
        
    Raises:
        KeyError: If required config keys are missing
    """
    config_path = Path(config_path)
    with config_path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    return validate_config_dict(cfg)


def build_output_paths(
    output_dir: Path,
    config: Dict[str, Any],
    *,
    timestamp: str | None = None,
) -> Dict[str, Path]:
    """
    Build output file paths for a pipeline run.

    Args:
        output_dir: Directory where outputs should be written
        config: Validated configuration dictionary
        timestamp: Optional fixed timestamp for deterministic naming

    Returns:
        Dictionary containing resolved output paths and run timestamp
    """
    return build_run_artifact_paths(output_dir, config, timestamp=timestamp)


# Path resolution
def find_project_root(start_path: Path | None = None) -> Path:
    """
    Discover project root by looking for standard directory structure.
    
    Args:
        start_path: Starting directory (defaults to current working directory)
        
    Returns:
        Project root directory
        
    Raises:
        FileNotFoundError: If project structure not found
    """
    start = Path(start_path).resolve() if start_path else Path.cwd().resolve()

    for candidate in [start, *start.parents]:
        if (
            (candidate / "config").exists()
            and (candidate / "inputs").exists()
            and (candidate / "src").exists()
        ):
            return candidate

    raise FileNotFoundError(
        "Could not find project root containing config/, inputs/, and src/"
    )


def resolve_project_paths(project_root: Path, config: Dict[str, Any]) -> Dict[str, Path | str]:
    """
    Resolve all project paths based on configuration.
    
    Args:
        project_root: Path to project root
        config: Configuration dictionary from load_config()
        
    Returns:
        Dictionary with resolved paths for all inputs and outputs
    """
    project_root = Path(project_root)

    layout_path = project_root / "inputs" / "layouts" / config["layout_file"]
    meta_path = project_root / "inputs" / "meta" / config["meta_file"]
    plate_specs_path = project_root / "data" / "source_plate_specs.json"

    output_paths = build_output_paths(project_root / "outputs" / "results", config)

    return {
        "project_root": project_root,
        "layout_path": layout_path,
        "meta_path": meta_path,
        "plate_specs_path": plate_specs_path,
        "out_idot": output_paths["out_idot"],
        "out_liquids": output_paths["out_liquids"],
        "out_imeta": output_paths["out_imeta"],
        "run_timestamp": str(output_paths["run_timestamp"]),
    }


# Plate specifications
def load_source_plate_specs(spec_path: Path) -> Dict[str, Any]:
    """
    Load source plate specifications from JSON file.
    
    Args:
        spec_path: Path to source_plate_specs.json
        
    Returns:
        Specifications dictionary keyed by plate type
    """
    spec_path = Path(spec_path)
    with spec_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_source_plate_spec(specs: Dict[str, Any], sourceplate_type: str) -> Dict[str, Any]:
    """
    Get specifications for a specific source plate type.
    
    Args:
        specs: Specifications dictionary from load_source_plate_specs()
        sourceplate_type: Plate type name (e.g. "S.100 Plate")
        
    Returns:
        Plate specifications
        
    Raises:
        KeyError: If plate type not found
    """
    if sourceplate_type not in specs:
        raise KeyError(f"Unknown source plate type: {sourceplate_type}")
    return specs[sourceplate_type]
