"""
Main PlateDesigner class for generating microplate layouts.
"""
from typing import Optional
import json
from pathlib import Path

# Support both package and direct imports
try:
    from .config import PlateConfig, PlateConfigJSON
    from .solver import MiniZincSolver
    from .output import Layout
    from .validators import validate_plate_config, validate_minizinc_available
    from .exceptions import SolverError, ValidationError
except ImportError:
    from config import PlateConfig, PlateConfigJSON
    from solver import MiniZincSolver
    from output import Layout
    from validators import validate_plate_config, validate_minizinc_available
    from exceptions import SolverError, ValidationError


class PlateDesigner:
    """
    Main interface for designing microplate layouts.
    
    Example:
        ```python
        from plaid_core import PlateDesigner, PlateConfig, Compound, Control
        
        config = PlateConfig(
            plate_rows=8, plate_cols=12, empty_edge=1,
            compounds=[
                Compound(name="CompA", concentrations=3, replicates=3),
            ],
            controls=[
                Control(name="PosCtrl", concentration_levels=1, replicates=3)
            ]
        )
        
        designer = PlateDesigner()
        layout = designer.design(config)
        layout.save_csv("output.csv")
        print(layout.summary())
        ```
    """
    
    def __init__(self, minizinc_path: Optional[str] = None):
        """
        Initialize PlateDesigner.
        
        Args:
            minizinc_path: Optional path to minizinc executable.
                          If not provided, searches PATH.
                          
        Raises:
            MiniZincNotFoundError: If minizinc not found
        """
        # Check MiniZinc availability
        if not validate_minizinc_available():
            raise SolverError(
                "MiniZinc not found. Install from https://www.minizinc.org/"
            )
        
        self.solver = MiniZincSolver(minizinc_path)
    
    def design(self, config: PlateConfig) -> Layout:
        """
        Generate microplate layout.
        
        Args:
            config: PlateConfig instance
            
        Returns:
            Layout object with design results
            
        Raises:
            ValidationError: If configuration is invalid
            SolverError: If solver fails
            NoSolutionFoundError: If no valid layout exists
            TimeoutError: If solver exceeds timeout
        """
        # Validate configuration
        validate_plate_config(config)
        
        # Run solver
        csv_output = self.solver.solve(config)
        
        # Parse and return layout
        layout = Layout(csv_output)
        return layout
    
    def load_config_from_json(self, json_path: str) -> PlateConfig:
        """
        Load configuration from JSON file.
        
        Args:
            json_path: Path to JSON config file
            
        Returns:
            PlateConfig instance
            
        Raises:
            ValidationError: If JSON is invalid
        """
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        config_model = PlateConfigJSON(**data)
        return config_model.to_config()
    
    def save_config_to_json(self, config: PlateConfig, json_path: str) -> None:
        """
        Save configuration to JSON file.
        
        Args:
            config: PlateConfig instance
            json_path: Output path
        """
        data = {
            'plate_rows': config.plate_rows,
            'plate_cols': config.plate_cols,
            'empty_edge': config.empty_edge,
            'compounds': [
                {
                    'name': c.name,
                    'concentrations': c.concentrations,
                    'replicates': c.replicates,
                    'concentration_names': c.concentration_names,
                }
                for c in config.compounds
            ],
            'controls': [
                {
                    'name': c.name,
                    'concentration_levels': c.concentration_levels,
                    'replicates': c.replicates,
                    'concentration_names': c.concentration_names,
                }
                for c in config.controls
            ],
            'concentrations_on_different_rows': config.concentrations_on_different_rows,
            'concentrations_on_different_columns': config.concentrations_on_different_columns,
            'replicates_on_same_plate': config.replicates_on_same_plate,
            'replicates_on_different_plates': config.replicates_on_different_plates,
            'allow_empty_wells': config.allow_empty_wells,
            'balance_controls_inside_plate': config.balance_controls_inside_plate,
            'interconnected_plates': config.interconnected_plates,
            'control_slack': config.control_slack,
            'force_spread_controls': config.force_spread_controls,
            'force_spread_concentrations': config.force_spread_concentrations,
            'horizontal_cell_lines': config.horizontal_cell_lines,
            'vertical_cell_lines': config.vertical_cell_lines,
            'timeout_seconds': config.timeout_seconds,
            'num_threads': config.num_threads,
            'random_seed': config.random_seed,
            'testing': config.testing,
            'sorted_compounds': config.sorted_compounds,
        }
        
        output_path = Path(json_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
