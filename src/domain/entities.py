from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class PropertiesData:
    source_filepath: str
    result_filepath: str
    materials: List[Dict[str, Any]]


@dataclass
class _SingleTextureChange:
    texturefilepath: str
    materials: List[Dict[str, Any]]


@dataclass
class TexturesData:
    glbfilepath: str
    files: List[_SingleTextureChange]
