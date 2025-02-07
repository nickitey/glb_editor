# Здесь находится уровень непосредственной работы с данными
import json
import os
from copy import deepcopy

from fastapi import status
from pygltflib import GLTF2
from pygltflib.utils import Image, ImageFormat

from src.core.exceptions import GLBEditorException
from src.core.settings import settings
from src.data.helpers import get_filename_from_timestamp
from src.domain.entities import PropertiesData, TexturesData
from src.domain.repositories import (IGLBParamsRepository,
                                     IGLBTexturesRepository)


class GLBParamsRepository(IGLBParamsRepository):

    @classmethod
    def _unite_dict(cls, dic1: dict, dic2: dict) -> dict:
        temp = deepcopy(dic1)
        for key in dic2:
            try:
                assert type(dic2[key]) == type(temp[key]) or (
                    type(dic2[key]) in (int, float)
                    and type(temp[key]) in (int, float)
                )
            except AssertionError:
                raise GLBEditorException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Заменяющие параметры GLB-файла должны быть одного типа данных",
                )
            if isinstance(temp[key], dict):
                temp[key] = cls._unite_dict(temp[key], dic2[key])
            elif isinstance(temp[key], list):
                temp[key] = [*dic2[key], *temp[key][len(dic2[key]):]]
            else:
                temp[key] = dic2[key]
        return temp

    async def change_parameters(self, request_data_object: PropertiesData):
        filepath = os.path.join(
            settings.editor.source_dir, request_data_object.filepath
        )
        gltf = GLTF2().load(filepath)
        gltf_dict = json.loads(gltf.gltf_to_json())
        materials = gltf_dict["materials"]
        changing_params_names = [
            material["name"] for material in request_data_object.materials
        ]
        for i in range(len(materials)):
            if materials[i]["name"] in changing_params_names:
                current_changes = next(
                    filter(
                        lambda changing_elem: materials[i]["name"]
                        == changing_elem["name"],
                        request_data_object.materials,
                    )
                )
                materials[i] = self._unite_dict(materials[i], current_changes)
        gltf_dict["materials"] = materials
        try:
            back_convert = gltf.gltf_from_json(json.dumps(gltf_dict))
            back_convert.set_binary_blob(gltf.binary_blob())
            new_filename = get_filename_from_timestamp(
                request_data_object.filepath
            )
            result_filepath = os.path.join(
                settings.editor.results_dir, new_filename
            )
            back_convert.save(result_filepath)
        except Exception as e:
            raise GLBEditorException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"Exceprion occured: {e}",
            )
        return {"status": "Готово", "filename": new_filename}


class GLBTexturesRepository(IGLBTexturesRepository):
    async def change_textures(self, request_data_object: TexturesData):
        glbfilepath = os.path.join(
            settings.editor.source_dir, request_data_object.glbfilepath
        )
        texture_filepath = os.path.join(
            settings.editor.textures_dir, request_data_object.texturefilepath
        )
        gltf = GLTF2().load(glbfilepath)
        gltf_dict = json.loads(gltf.gltf_to_json())
        materials = gltf_dict["materials"]

        new_image = Image()
        new_image.uri = texture_filepath

        for i in range(len(request_data_object.materials)):
            old_picture_material = next(
                filter(
                    lambda material: material["name"]
                    == request_data_object.materials[i]["name"],
                    materials,
                )
            )
            if old_picture_material.get("pbrMetallicRoughness") is not None:
                old_picture_texture_idx = old_picture_material[
                    "pbrMetallicRoughness"
                ]["baseColorTexture"]["index"]
            if old_picture_material.get("normalTexture") is not None:
                old_picture_texture_idx = old_picture_material[
                    "normalTexture"
                ]["index"]

            old_picture_idx = gltf.textures[old_picture_texture_idx].source

            try:
                gltf.images[old_picture_idx] = new_image
                gltf.convert_images(
                    image_format=ImageFormat.DATAURI, override=True
                )
                new_filename = get_filename_from_timestamp(
                    request_data_object.glbfilepath
                )
                result_filepath = os.path.join(
                    settings.editor.results_dir, new_filename
                )
                gltf.save(result_filepath)
            except Exception as e:
                raise GLBEditorException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    f"Exceprion occured: {e}",
                )
            return {"status": "Готово", "filename": new_filename}
