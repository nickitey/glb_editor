from typing import List, Optional

from pydantic import BaseModel


class NormalMaterialTextureModel(BaseModel):
    index: Optional[int] = None
    texCoord: Optional[int] = None
    scale: Optional[float] = 1.0


class TextureInfoModel(BaseModel):
    index: int = None
    texCoord: Optional[int] = 0


class PbrMetallicRoughnessModel(BaseModel):
    baseColorFactor: Optional[List[int | float]] = None
    metallicFactor: Optional[int | float] = None
    roughnessFactor: Optional[int | float] = None
    baseColorTexture: Optional[TextureInfoModel] = None


class MaterialModel(BaseModel):
    name: str
    pbrMetallicRoughness: PbrMetallicRoughnessModel | None = None
    normalMaterialTexture: NormalMaterialTextureModel | None = None


class MaterialsRequestModel(BaseModel):
    filepath: str
    materials: List[MaterialModel]


class TexturesRequestModel(BaseModel):
    glbfilepath: str
    texturefilepath: str
    materials: List[MaterialModel]
