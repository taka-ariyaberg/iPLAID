"""
MiniZinc solver wrapper.
"""
import subprocess
import json
import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple
import shutil
import multiprocessing

# Support both package and direct imports
try:
    from .config import PlateConfig, Compound, Control
    from .exceptions import (
        MiniZincNotFoundError, SolverError, NoSolutionFoundError, TimeoutError
    )
except ImportError:
    from config import PlateConfig, Compound, Control
    from exceptions import (
        MiniZincNotFoundError, SolverError, NoSolutionFoundError, TimeoutError
    )


class MiniZincSolver:
    """Wrapper for MiniZinc constraint solver."""
    
    def __init__(self, minizinc_path: Optional[str] = None):
        """
        Initialize solver.
        
        Args:
            minizinc_path: Path to minizinc executable. If None, searches PATH.
        """
        self.minizinc_path = minizinc_path or self._find_minizinc()
        if not self.minizinc_path:
            raise MiniZincNotFoundError(
                "MiniZinc not found. Install from https://www.minizinc.org/ "
                "or set MINIZINC_PATH environment variable"
            )
    
    @staticmethod
    def _find_minizinc() -> Optional[str]:
        """Find MiniZinc executable in PATH or common locations."""
        # Check environment variable first
        if 'MINIZINC_PATH' in os.environ:
            path = os.environ['MINIZINC_PATH']
            if os.path.exists(path):
                return path
        
        # Check PATH
        minizinc = shutil.which("minizinc")
        if minizinc:
            return minizinc
        
        # Check macOS common location
        macos_path = "/Applications/MiniZincIDE.app/Contents/Resources/minizinc"
        if os.path.exists(macos_path):
            return macos_path
        
        return None
    
    def solve(self, config: PlateConfig) -> str:
        """
        Solve plate design using MiniZinc.
        
        Args:
            config: PlateConfig instance
            
        Returns:
            CSV output from solver
            
        Raises:
            SolverError: If solving fails
            NoSolutionFoundError: If no solution found
            TimeoutError: If timeout exceeded
        """
        # Generate .dzn file
        dzn_content = self._generate_dzn(config)
        
        # Get path to plate-design.mzn template
        template_dir = Path(__file__).parent / "templates"
        mzn_file = template_dir / "plate-design.mzn"
        
        if not mzn_file.exists():
            raise SolverError(f"Model file not found: {mzn_file}")
        
        # Create temporary .dzn file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.dzn', delete=False) as f:
            f.write(dzn_content)
            dzn_file = f.name
        
        try:
            # Clamp threads to available CPUs — Gecode crashes with =====ERROR=====
            # if asked for more workers than the OS can schedule.
            available_cpus = multiprocessing.cpu_count()
            threads = min(config.num_threads, available_cpus)

            # Build command
            cmd = [
                self.minizinc_path,
                "--solver", "Gecode",
                str(mzn_file),
                dzn_file,
                "-p", str(threads),
                "-t", str(config.timeout_seconds * 1000),
            ]
            
            # Add random seed if provided
            if config.random_seed is not None:
                cmd.extend(["-r", str(config.random_seed)])
            
            # Add testing mode if enabled
            if config.testing:
                cmd.extend(["--cmdline-data", "testing=true"])
            
            # Run solver
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config.timeout_seconds + 5  # Add buffer
            )
            
            # Check output
            if "=====UNKNOWN=====" in result.stdout:
                raise NoSolutionFoundError(
                    "MiniZinc solver could not find a solution within timeout. "
                    "Try reducing constraints or increasing timeout."
                )

            if "=====UNSATISFIABLE=====" in result.stdout:
                raise NoSolutionFoundError(
                    "No valid plate layout exists with the given constraints. "
                    "Try relaxing constraints (e.g. allow empty wells, reduce replicates)."
                )

            if "=====ERROR=====" in result.stdout or result.returncode != 0:
                # MiniZinc writes errors to stdout, not stderr
                detail = (result.stdout.strip() or result.stderr.strip() or
                          f"exit code {result.returncode}")
                raise SolverError(f"MiniZinc solver failed: {detail}")

            return result.stdout.strip()
        
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Solver exceeded timeout of {config.timeout_seconds}s")
        except (SolverError, NoSolutionFoundError, TimeoutError):
            raise
        except Exception as e:
            raise SolverError(f"Solver error: {str(e)}")
        finally:
            # Clean up temp file
            try:
                os.unlink(dzn_file)
            except:
                pass
    
    @staticmethod
    def _generate_dzn(config: PlateConfig) -> str:
        """
        Generate MiniZinc .dzn data file content.
        
        Args:
            config: PlateConfig instance
            
        Returns:
            String content of .dzn file
        """
        lines = []
        
        # Plate configuration
        lines.append(f"num_rows = {config.plate_rows};")
        lines.append(f"num_cols = {config.plate_cols};")
        lines.append(f"size_empty_edge = {config.empty_edge};")
        lines.append(f"horizontal_cell_lines = {config.horizontal_cell_lines};")
        lines.append(f"vertical_cell_lines = {config.vertical_cell_lines};")
        lines.append(f"allow_empty_wells = {str(config.allow_empty_wells).lower()};")
        lines.append("")
        
        # Constraints
        lines.append(f"concentrations_on_different_rows = {str(config.concentrations_on_different_rows).lower()};")
        lines.append(f"concentrations_on_different_columns = {str(config.concentrations_on_different_columns).lower()};")
        lines.append(f"replicates_on_same_plate = {str(config.replicates_on_same_plate).lower()};")
        lines.append(f"replicates_on_different_plates = {str(config.replicates_on_different_plates).lower()};")
        lines.append("")
        
        # Compounds
        lines.append(f"compounds = {len(config.compounds)};")
        
        if config.compounds:
            rep_list = ", ".join(str(c.replicates) for c in config.compounds)
            lines.append(f"compound_replicates = [{rep_list}];")
            
            conc_list = ", ".join(str(c.concentrations) for c in config.compounds)
            lines.append(f"compound_concentrations = [{conc_list}];")
            
            names = ", ".join(f'"{c.name}"' for c in config.compounds)
            lines.append(f'compound_names = [{names}];')
            
            # Concentration names (2D array)
            conc_names_rows = []
            for compound in config.compounds:
                names = ", ".join(f'"{name}"' for name in compound.concentration_names)
                conc_names_rows.append(names)
            conc_names_str = "|".join(conc_names_rows)
            lines.append(f'compound_concentration_names = [|{conc_names_str}|];')
        else:
            lines.append("compound_replicates = [];")
            lines.append("compound_concentrations = [];")
            lines.append("compound_names = [];")
            lines.append("compound_concentration_names = [];")
        
        max_conc = max([c.concentrations for c in config.compounds], default=1)
        lines.append(f'compound_concentration_indicators = ["" | i in 1..{max_conc}];')
        lines.append("")
        
        # Combinations (deprecated, always 0)
        lines.append("combinations = 0;")
        lines.append("combination_concentrations = 0;")
        lines.append("combination_names = [];")
        lines.append("combination_concentration_names = [];")
        lines.append("")
        
        # Controls
        lines.append(f"num_controls = {len(config.controls)};")
        
        if config.controls:
            rep_list = ", ".join(str(c.replicates) for c in config.controls)
            lines.append(f"control_replicates = [{rep_list}];")
            
            conc_list = ", ".join(str(c.concentration_levels) for c in config.controls)
            lines.append(f"control_concentrations = [{conc_list}];")
            
            names = ", ".join(f'"{c.name}"' for c in config.controls)
            lines.append(f'control_names = [{names}];')
            
            # Control concentration names
            conc_names_rows = []
            for control in config.controls:
                names = ", ".join(f'"{name}"' for name in control.concentration_names)
                conc_names_rows.append(names)
            conc_names_str = "|".join(conc_names_rows)
            lines.append(f'control_concentration_names = [|{conc_names_str}|];')
        else:
            lines.append("control_replicates = [];")
            lines.append("control_concentrations = [];")
            lines.append("control_names = [];")
            lines.append("control_concentration_names = [];")
        
        lines.append("")
        
        # Advanced control parameters (balance_controls_inside_plate, interconnected_plates,
        # control_slack, force_spread_controls, force_spread_concentrations are
        # computed/defaulted inside plate-design.mzn and must not be set in .dzn)
        
        # Testing parameters (optional)
        if config.testing:
            lines.append(f"testing = true;")
        if config.sorted_compounds is not None:
            lines.append(f"sorted_compounds = {str(config.sorted_compounds).lower()};")
        
        return "\n".join(lines)
