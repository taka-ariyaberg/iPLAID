"""
Layout output handling and formatting.
"""
import csv
import json
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd

# Support both package and direct imports
try:
    from .exceptions import LayoutError
except ImportError:
    from exceptions import LayoutError


class Layout:
    """Represents a generated microplate layout."""
    
    def __init__(self, csv_output: str):
        """
        Initialize from MiniZinc CSV output.
        
        Args:
            csv_output: CSV string from solver
        """
        self.raw_csv = csv_output
        self._parse_csv()
    
    def _parse_csv(self) -> None:
        """Parse CSV output from MiniZinc."""
        lines = self.raw_csv.strip().split('\n')
        if not lines or lines[0].startswith('====='):
            raise LayoutError("Invalid layout output from solver")
        
        # Remove trailing separator line
        if lines and lines[-1].startswith('---'):
            lines = lines[:-1]
        
        # Parse CSV
        reader = csv.DictReader(lines)
        self.wells: List[Dict] = list(reader)
        
        if not self.wells:
            raise LayoutError("No layout data in solver output")
        
        # Extract unique plate IDs
        self.plate_ids = sorted(set(w['plateID'] for w in self.wells))
        self.num_plates = len(self.plate_ids)
    
    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert to pandas DataFrame.
        
        Returns:
            DataFrame with columns: plateID, well, cmpdname, CONCuM, cmpdnum, VOLuL
        """
        return pd.DataFrame(self.wells)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary format."""
        return {
            'num_plates': self.num_plates,
            'num_wells': len(self.wells),
            'wells': self.wells,
            'plate_ids': self.plate_ids,
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    def save_csv(self, path: str) -> str:
        """
        Save layout to CSV file.
        
        Args:
            path: Output file path
            
        Returns:
            Path to saved file
        """
        df = self.to_dataframe()
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        return str(output_path)
    
    def save_json(self, path: str) -> str:
        """
        Save layout to JSON file.
        
        Args:
            path: Output file path
            
        Returns:
            Path to saved file
        """
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(self.to_json())
        return str(output_path)
    
    def get_plate_data(self, plate_id: str) -> pd.DataFrame:
        """
        Get data for specific plate.
        
        Args:
            plate_id: Plate identifier (e.g., 'plate_1')
            
        Returns:
            DataFrame with wells for this plate only
        """
        df = self.to_dataframe()
        return df[df['plateID'] == plate_id]
    
    def summary(self) -> str:
        """Get summary of layout."""
        df = self.to_dataframe()
        
        lines = [
            f"Plate Layout Summary",
            f"{'='*50}",
            f"Total Plates: {self.num_plates}",
            f"Total Wells Used: {len(self.wells)}",
            f"Plate IDs: {', '.join(self.plate_ids)}",
            f"",
            "Wells per Plate:",
        ]
        
        for plate_id in self.plate_ids:
            count = len(df[df['plateID'] == plate_id])
            lines.append(f"  {plate_id}: {count} wells")
        
        lines.append("")
        lines.append("Sample Types:")
        for sample_type in df['cmpdname'].unique():
            count = len(df[df['cmpdname'] == sample_type])
            lines.append(f"  {sample_type}: {count} wells")
        
        return "\n".join(lines)
    
    def __repr__(self) -> str:
        return f"Layout({self.num_plates} plates, {len(self.wells)} wells)"
