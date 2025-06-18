from typing import List, Optional, Union

from pydantic import BaseModel


class NormalMaterialTextureModel(BaseModel):
    index: Optional[int] = None
    texCoord: Optional[int] = None
    scale: Optional[float] = 1.0


class TextureInfoModel(BaseModel):
    index: int = None
    texCoord: Optional[int] = 0


class PbrMetallicRoughnessModel(BaseModel):
    baseColorFactor: Optional[List[Union[int, float]]] = None
    metallicFactor: Optional[Union[int, float]] = None
    roughnessFactor: Optional[Union[int, float]] = None
    baseColorTexture: Optional[TextureInfoModel] = None


class MaterialModel(BaseModel):
    name: str
    pbrMetallicRoughness: Optional[PbrMetallicRoughnessModel] = None
    normalMaterialTexture: Optional[NormalMaterialTextureModel] = None


class MaterialsRequestModel(BaseModel):
    source_filepath: str
    result_filepath: str
    materials: List[MaterialModel]


class _SingleTextureChange(BaseModel):
    texturefilepath: str
    materials: List[MaterialModel]


class TexturesRequestModel(BaseModel):
    source_glbfilepath: str
    result_filepath: str
    files: List[_SingleTextureChange]
