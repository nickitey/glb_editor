# Здесь находится уровень непосредственной работы с данными
import json
from copy import deepcopy

from fastapi import status
from pygltflib import GLTF2

from src.core.exceptions import GLBEditorException
from src.domain.entities import PropertiesData
from src.domain.repositories import IGLBParamsRepository


class GLBParamsRepository(IGLBParamsRepository):

    @classmethod
    def _unite_dict(cls, dic1: dict, dic2: dict) -> dict:
        temp = deepcopy(dic1)
        for key in dic2:
            try:
                # TODO: Проверить это дерьмо.
                assert type(dic2[key]) == type(temp[key]) or (
                    type(dic2[key]) in (int, float)
                    and type(temp[key]) in (int, float)
                )
            except AssertionError:
                print(dic2[key], temp[key], sep="\n\n")
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
        gltf = GLTF2().load(request_data_object.filepath)
        gltf_dict = json.loads(gltf.gltf_to_json())
        materials = gltf_dict["materials"]
        print(f"{materials=}")
        print()
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
        print(f"{materials=}")
        print()
        gltf_dict["materials"] = materials

        back_convert = gltf.gltf_from_json(json.dumps(gltf_dict))
        back_convert.set_binary_blob(gltf.binary_blob())
        back_convert.save("Stul_red1.glb")
