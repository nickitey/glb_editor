from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class PropertiesData:
    filepath: str
    materials: List[Dict[str, Any]]

    def __repr__(self):
        return f"{self.filepath=}, {self.materials=}"
