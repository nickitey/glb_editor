from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class PropertiesData:
    filepath: str
    materials: List[Dict[str, Any]]

    def __repr__(self):
        return f"{self.filepath=},\n{self.materials=}"


@dataclass
class TexturesData:
    glbfilepath: str
    texturefilepath: str
    materials: List[Dict[str, Any]]

    def __repr__(self):
        return f"{self.glbfilepath=},\n{self.texturefilepath=},\n{self.materials=}"
