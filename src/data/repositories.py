# Здесь находится уровень непосредственной работы с данными
import json
import os
from copy import deepcopy
from typing import Dict

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
                    type(dic2[key]) in (int, float) and type(temp[key]) in (int, float)
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
            new_filename = get_filename_from_timestamp(request_data_object.filepath)
            result_filepath = os.path.join(settings.editor.results_dir, new_filename)
            back_convert.save(result_filepath)
        except Exception as e:
            raise GLBEditorException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"Exceprion occured: {e}",
            )
        return {"status": "Готово", "filename": new_filename}


class GLBTexturesRepository(IGLBTexturesRepository):
    async def change_textures(self, request_data_object: TexturesData):
        self._request_DTO = request_data_object
        glbfilepath = os.path.join(
            settings.editor.source_dir, self._request_DTO.glbfilepath
        )
        gltf = GLTF2().load(glbfilepath)

        # Работа по замене текстуры складывается из двух этапов:
        # 1. Декларировать, какие изображения текстур изменяются (работа с JSON
        # структурой файла);
        # 2. Закрепить изменения, сконвертировав изображение.

        try:
            # Первый этап - вносим изменения в структуру. Экономим память,
            # не создавая в ней новый объект (сборщик мусора сотрет старый).
            gltf = self._process_gltf(gltf)

            # Второй этап - конвертация изображения в необходимый формат,
            # который сможет храниться внутри единого GLB-файла.
            # К сожалению, библиотека pygltflib не поддерживает формат Bufferview.
            # Остается только кодирование в DataURI.
            new_filename = self._process_glb(gltf)

        except Exception as e:
            raise GLBEditorException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"Exceprion occured: {e}",
            )
        return {"status": "Готово", "filename": new_filename}

    def _process_gltf(self, gltf: GLTF2) -> GLTF2:
        texture_filepath = os.path.join(
            settings.editor.textures_dir, self._request_DTO.texturefilepath
        )
        # gltf_dict = json.loads(gltf.gltf_to_json())
        # materials = gltf_dict["materials"]

        new_image = Image()
        new_image.uri = texture_filepath

        # Если материалов, в которых необходимо заменить текстуру, много,
        # мы сначала готовим указанные изменения, а затем конвертируем
        # изображения в бинарный контент.
        for replacement_material in self._request_DTO.materials:
            old_picture_material = next(
                filter(
                    lambda material: material.name == replacement_material["name"],
                    gltf.materials,
                )
            )

            metallic_material = getattr(old_picture_material, "pbrMetallicRoughness")
            metallic_texture = getattr(
                metallic_material, "baseColorTexture"
            ) or getattr(metallic_material, "metallicRoughnessTexture")
            normal_texture = getattr(old_picture_material, "normalTexture")
            if metallic_texture and normal_texture:
                try:
                    assert metallic_texture.index == normal_texture.index
                except AssertionError:
                    raise GLBEditorException(
                        'Материалы типа "pbrMetallicRoughness" и "normalTexture"'
                        " ссылаются на разные текстуры. Возникла неопределенность"
                        " в определении заменяемой текстуры GLB-файла",
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    )
                else:
                    old_picture_texture_idx = metallic_texture.index
            elif metallic_texture or normal_texture:
                existing_material = metallic_texture or normal_texture
                old_picture_texture_idx = existing_material.index
            else:
                raise GLBEditorException(
                    "В редактируемом файле отсутствет материал, указанный "
                    "в поступившем запросе. Попробуйте в начале добавить "
                    "материал в структуру файла, а затем изменить текстуру, "
                    "на которую ссылается данный материал."
                )
                # TODO: Реализовать подобный функционал вместо ошибки.

            old_picture_idx = gltf.textures[old_picture_texture_idx].source
            gltf.images[old_picture_idx] = new_image

        return gltf

    def _process_glb(self, gltf: GLTF2) -> Dict[str, str]:
        gltf.convert_images(image_format=ImageFormat.DATAURI, override=True)
        new_filename = get_filename_from_timestamp(self._request_DTO.glbfilepath)
        result_filepath = os.path.join(settings.editor.results_dir, new_filename)
        gltf.save(result_filepath)
        return new_filename
