from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class PropertiesData:
    filepath: str
    materials: List[Dict[str, Any]]


@dataclass
class _SingleTextureChange:
    texturefilepath: str
    materials: List[Dict[str, Any]]


@dataclass
class TexturesData:
    glbfilepath: str
    files: List[_SingleTextureChange]
