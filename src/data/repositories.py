# Здесь находится уровень непосредственной работы с данными
import json
import os
from copy import deepcopy

from fastapi import status
from pygltflib import (GLTF2, Material, NormalMaterialTexture,
                       PbrMetallicRoughness, TextureInfo)
from pygltflib.utils import Image, ImageFormat, Texture

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
                detail=f"Exception occurred: {e}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return {"status": "Готово", "filename": new_filename}


class GLBTexturesRepository(IGLBTexturesRepository):
    async def change_textures(self, request_data_object: TexturesData):
        glbfilepath = os.path.join(
            settings.editor.source_dir, request_data_object.glbfilepath
        )
        gltf = GLTF2().load(glbfilepath)

        # Работа по замене текстуры складывается из двух этапов:
        # 1. Декларировать, какие изображения текстур изменяются (работа с JSON
        # структурой файла);
        # 2. Закрепить изменения, сконвертировав изображение.

        try:
            # Первый этап - вносим изменения в структуру. Экономим память,
            # не создавая в ней новый объект (сборщик мусора сотрет старый).
            gltf = self._process_gltf(gltf, request_data_object)

            # Второй этап - конвертация изображения в необходимый формат,
            # который сможет храниться внутри единого GLB-файла.
            # К сожалению, библиотека pygltflib не поддерживает формат Bufferview.
            # Остается только кодирование в DataURI.
            new_filename = self._process_glb(gltf, request_data_object)

        except GLBEditorException as e:
            raise e
        except Exception as e:
            raise GLBEditorException(
                detail=f"Exception occured: {e}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return {"status": "Готово", "filename": new_filename}

    def _replace_image_in_texture(
        self,
        gltf: GLTF2,
        material_name: str,
        texture_name: str,
        image: Image,
        submaterial: str | None = None,
    ) -> GLTF2:
        target_materials = list(
            filter(
                lambda material: material.name == material_name, gltf.materials
            )
        )
        try:
            assert len(target_materials) != 0
        except AssertionError:
            raise GLBEditorException(
                detail="В редактируемом файле отсутствет материал с именем "
                f"{material_name}, указанным в поступившем запросе",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
            # TODO: Реализовать подобный функционал вместо ошибки.
        target_material = target_materials[0]
        source_texture = (
            getattr(getattr(target_material, submaterial), texture_name)
            if submaterial
            else getattr(target_material, texture_name)
        )
        if source_texture is None:
            return self._add_texture_to_material(
                gltf, target_material, texture_name, image, submaterial
            )
        else:
            image_index = gltf.textures[source_texture.index].source
            repeated_image_indexes = list(
                filter(
                    lambda texture: texture.source == image_index,
                    gltf.textures
                )
            )
            repeated_texture_indexes = list(
                filter(
                    lambda material: source_texture.index ==
                        material.pbrMetallicRoughness.baseColorTexture.index 
                        if (isinstance(getattr(material, "pbrMetallicRoughness"), PbrMetallicRoughness) 
                            and isinstance(getattr(material.pbrMetallicRoughness, "baseColorTexture"), TextureInfo)) 
                        else material.pbrMetallicRoughness.metallicRoughnessTexture 
                            if (isinstance(getattr(material, "pbrMetallicRoughness"), PbrMetallicRoughness) 
                                and isinstance(getattr(material.pbrMetallicRoughness, "metallicRoughnessTexture"), TextureInfo)) 
                            else material.normalTexture.index 
                                if isinstance(getattr(material, "normalTexture"), NormalMaterialTexture) else None,
                gltf.materials)
            )
            if len(repeated_image_indexes) > 1 or len(repeated_texture_indexes) > 1:
                return self._add_texture_to_material(
                    gltf, target_material, texture_name, image, submaterial
                )
            else:
                from pprint import pprint
                pprint(repeated_texture_indexes)
                return self._add_image_to_texture(
                    gltf, repeated_image_indexes[0], image
                )

    @staticmethod
    def _add_image_to_texture(gltf: GLTF2, texture_to_change: Texture, image: Image):
        gltf.images.append(image)
        texture_idx = gltf.textures.index(texture_to_change)
        gltf.textures[texture_idx].source = len(gltf.images) - 1
        return gltf
        
    @staticmethod
    def _add_texture_to_material(
        gltf: GLTF2,
        material: Material,
        texture_name: str,
        image: Image,
        submaterial: str = None,
    ) -> GLTF2:
        examples = {
            "pbrMetallicRoughness": PbrMetallicRoughness,
            "normalTexture": NormalMaterialTexture,
        }

        gltf.images.append(image)

        texture = Texture()
        texture.source = len(gltf.images) - 1
        gltf.textures.append(texture)

        material_idx = gltf.materials.index(material)
        if submaterial:
            new_texture = examples[submaterial]()
            new_nexture_info = TextureInfo()
            new_nexture_info.index = len(gltf.textures) - 1
            setattr(new_texture, texture_name, new_nexture_info)
            setattr(gltf.materials[material_idx], submaterial, new_texture)
        else:
            new_texture = examples[texture_name]()
            new_texture.index = len(gltf.textures) - 1
            setattr(gltf.materials[material_idx], texture_name, new_texture)
        return gltf

    @staticmethod
    def _change_texture_in_material(
        gltf: GLTF2, texture: Texture, image: Image
    ) -> GLTF2:
        image_index = gltf.textures[texture.index].source
        gltf.images[image_index] = image
        return gltf

    def _process_gltf(self, gltf: GLTF2, request_DTO: TexturesData) -> GLTF2:
        for single_change in request_DTO.files:
            texture_filepath = os.path.join(
                settings.editor.textures_dir, single_change.texturefilepath
            )

            new_image = Image()
            new_image.uri = texture_filepath

            # Если материалов, в которых необходимо заменить текстуру, много,
            # мы сначала готовим указанные изменения, а затем конвертируем
            # изображения в бинарный контент.
            for replacement_material in single_change.materials:
                material_name = replacement_material["name"]

                # Определим, какие материалы требуется заменить.
                # В материале может быть два типа текстур металлическая
                # (pbrMetallicRoughness) или "нормальная" (normalTexture).
                # У металлической есть вложенность - там может быть либо
                # baseColorTexture, либо metallicRoughnessTexture, а уже
                # у какой-то из них искомый нам индекс.
                # Посмотрим, есть ли в материале металлическая текстура
                pbr_metallic_roughness = replacement_material.get(
                    "pbrMetallicRoughness"
                )
                # Если есть, то проверим, какого она типа:
                if pbr_metallic_roughness:
                    base_color_texture = pbr_metallic_roughness.get(
                        "baseColorTexture"
                    )
                    metallic_roughness_texture = pbr_metallic_roughness.get(
                        "metallicRoughnessTexture"
                    )
                    # Поскольку пустой словарь определяется как False в условных
                    # конструкциях, мы явно проверяем тип данных, а затем
                    # принимаем решение, какого типа текстуру будем искать
                    # в изменяемом файле
                    if isinstance(base_color_texture, dict):
                        metallic_texture = "baseColorTexture"
                    elif isinstance(metallic_roughness_texture, dict):
                        metallic_texture = "metallicRoughnessTexture"
                    else:
                        raise GLBEditorException(
                            detail="Необходимо уточнить в запросе, какой тип"
                            " текстуры в материале типа pbrMetallicRoughness"
                            " необходимо изменить.\n Поддерживаемые"
                            " типы текстур: metallicRoughnessTexture"
                            " и baseColorTexture.",
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        )
                else:
                    # Если такая текстура в принципе отсутствует в запросе,
                    # то мы явно объявим это в коде для наглядности.
                    metallic_texture = None

                # Теперь посмотрим, есть ли в материале "нормальная текстура".
                normal_texture = (
                    "normalTexture"
                    if isinstance(
                        replacement_material.get("normalTexture"), dict
                    )
                    else None
                )

                # А затем заменим требуемые, определив сами объекты текстур в файле.
                if metallic_texture:
                    gltf = self._replace_image_in_texture(
                        gltf,
                        material_name,
                        metallic_texture,
                        new_image,
                        "pbrMetallicRoughness",
                    )
                if normal_texture:
                    gltf = self._replace_image_in_texture(
                        gltf, material_name, "normalTexture", new_image
                    )
        return gltf

    @staticmethod
    def _process_glb(gltf: GLTF2, request_DTO: TexturesData) -> str:
        gltf.convert_images(image_format=ImageFormat.DATAURI, override=True)
        new_filename = get_filename_from_timestamp(request_DTO.glbfilepath)
        result_filepath = os.path.join(
            settings.editor.results_dir, new_filename
        )
        gltf.save(result_filepath)
        return new_filename
