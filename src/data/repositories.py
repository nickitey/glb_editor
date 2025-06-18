# Здесь находится уровень непосредственной работы с данными
import json
import os
from copy import deepcopy
from typing import Optional

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
        source_filepath = request_data_object.source_filepath
        if not os.path.exists(source_filepath):
            raise GLBEditorException(
                detail='Файл "%s" отсутствует на сервере' % source_filepath,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        gltf = GLTF2().load(source_filepath)
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
                request_data_object.source_filepath.split("/").pop()
            )
            if not os.path.exists(request_data_object.result_filepath):
                os.mkdir(request_data_object.result_filepath)

            result_filepath = os.path.join(request_data_object.result_filepath, new_filename)
            back_convert.save(result_filepath)
        except Exception as e:
            raise GLBEditorException(
                detail=f"Exception occurred: {e}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return {"status": "Готово", "result": result_filepath}


class GLBTexturesRepository(IGLBTexturesRepository):
    """
    Иерархия зависимости материалов и текстур в GLB/GLTF-файле следующая:
    Есть материал. У него есть свойства - карты текстур. Карты текстур
    ссылаются на текстуру. Текстура ссылается на изображение.
    Проблема в том, что карты текстур могут быть разными, строго говоря,
    двух видов: pbrMetallicRoughness, у которой могут быть два варианта
    вложенных параметров карт текстур (один из или два сразу),
    и normalTexture, которая сразу содержит ссылку на текстуру.
    Схематически:
                                Material
                                  /  \
                                 /    \
                                /      \
                               /        \
                              /          \
                             /            \
            pbrMetallicRoughness        normalTexture
                 /         \                  |
                /           \               index
               /             \
              /               \
        baseColorTexture   metallicRoughnessTexture
               |                       |
             index                   index
    """

    async def change_textures(self, request_data_object: TexturesData):
        source_glbfilepath = request_data_object.source_glbfilepath
        if not os.path.exists(source_glbfilepath):
            raise GLBEditorException(
                detail='Файл "%s" отсутствует на сервере' % source_glbfilepath,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        gltf = GLTF2().load(source_glbfilepath)

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
            result_filepath = self._process_glb(gltf, request_data_object)

        except GLBEditorException as e:
            raise e
        except Exception as e:
            raise GLBEditorException(
                detail=f"Exception occured: {e}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return {"status": "Готово", "result": result_filepath}

    def _process_gltf(self, gltf: GLTF2, request_DTO: TexturesData) -> GLTF2:
        for single_change in request_DTO.files:
            texture_filepath = single_change.texturefilepath
            if not os.path.exists(texture_filepath):
                raise GLBEditorException(
                    detail='Файл текстуры "%s" отсутствует на сервере' % texture_filepath,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            # В любом случае мы привносим в файл новое изображение, поэтому
            # целесообразно всегда создавать новый объект изображения, который
            # затем использовать в различных сценариях.
            new_image = Image()
            new_image.uri = texture_filepath
            filename_idx = texture_filepath.rfind("/")
            new_image.name = texture_filepath[filename_idx + 1:]

            # Если материалов, в которых необходимо заменить текстуру, много,
            # мы сначала готовим указанные изменения, а затем конвертируем
            # изображения в бинарный контент.
            for replacement_material in single_change.materials:
                material_name = replacement_material["name"]

                # Определим, какие материалы требуется заменить.
                # В материале может быть два типа текстур "металлическая"
                # (pbrMetallicRoughness) или "нормальная" (normalTexture).
                # Мы проверяем запрос, требуется ли от нас заменить карту
                # материала типа pbrMetallicRoughness.
                pbr_metallic_roughness = replacement_material.get(
                    "pbrMetallicRoughness"
                )
                # У этой карты по спецификации есть вложенность - внутри нее
                # может быть структура baseColorTexture или metallicRoughnessTexture.
                # Или вообще и то, и другое. И в каждой из них может находиться
                # индекс конкретной текстуры, которую нам необходимо заменить.
                # Поэтому мы создаем список, какие виды вложенных "металлических"
                # текстур есть в запросе и предполагаются к замене.
                # Создаем мы этот список здесь, чтобы он попал в область видимости
                # вне условной конструкции. Проверять наличие в нем элементов
                # мы будем на этапе уже конкретной замены элементов в файле.
                metallic_textures = []

                if pbr_metallic_roughness:
                    base_color_texture = pbr_metallic_roughness.get(
                        "baseColorTexture"
                    )
                    metallic_roughness_texture = pbr_metallic_roughness.get(
                        "metallicRoughnessTexture"
                    )
                    # Поскольку пустой словарь определяется как False в условных
                    # конструкциях, мы явно проверяем тип данных, не None ли
                    # вернулся нам при попытке получить значение по ключу
                    # "pbrMetallicRoughness".
                    is_base_color_texture = isinstance(
                        base_color_texture, dict
                    )
                    is_metallic_roughness_texture = isinstance(
                        metallic_roughness_texture, dict
                    )

                    if not (
                        is_base_color_texture or is_metallic_roughness_texture
                    ):
                        raise GLBEditorException(
                            detail="Необходимо уточнить в запросе, какой тип"
                            " текстуры в материале типа pbrMetallicRoughness"
                            " необходимо изменить.\n Поддерживаемые"
                            " типы текстур: metallicRoughnessTexture"
                            " и baseColorTexture.",
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        )

                    if is_base_color_texture:
                        metallic_textures.append("baseColorTexture")
                    if is_metallic_roughness_texture:
                        metallic_textures.append("metallicRoughnessTexture")

                # Теперь посмотрим, есть ли в материале "нормальная текстура".
                normal_texture = (
                    "normalTexture"
                    if isinstance(
                        replacement_material.get("normalTexture"), dict
                    )
                    else None
                )

                # А затем заменим требуемые, определив сами объекты текстур в файле.
                if metallic_textures:
                    for metallic_texture in metallic_textures:
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
        new_filename = get_filename_from_timestamp(request_DTO.source_glbfilepath.split("/").pop())
        if not os.path.exists(request_DTO.result_filepath):
            os.mkdir(request_DTO.result_filepath)

        result_filepath = os.path.join(request_DTO.result_filepath, new_filename)
        gltf.save(result_filepath)
        return result_filepath

    def _replace_image_in_texture(
        self,
        gltf: GLTF2,
        material_name: str,
        texture_info: str,
        image: Image,
        submaterial: Optional[str] = None,
    ) -> GLTF2:
        """
        Метод занимается узкой задачей замены текстуры в файле. Логика работы
        следующая:
        1) Определяется наличие в файле материала, который пришел в запросе;
        2) Определяется, на какие текстуры ссылается материал. Вот это и есть
        самая трудоемкая задача - как раз в силу абсолютной опциональности
        наличия той или иной карты текстур в редактируемом файле. Мы не можем
        просто перебрать все свойства материала, потому что не все они связаны
        с текстурами в принципе, они называются по-разному и имеют разную
        вложенность, то есть, добраться до искомого параметра source можно
        различными путями, что несколько усложняет задачу;
        3) Производится проверка, ссылается ли еще кто-либо на эту текстуру;
        4) Если никто не ссылается - то заменяется целиком изображение, ссылка
        в текстуре остается та же, но ведет она на новое изображение;
        5) Если другие материалы ссылаются на эту текстуру или другие текстуры
        ссылаются на одну картинку - добавляется новая картинка, на которую
        ссылается вновь созданная текстура, на которую в свою очередь начинает
        ссылаться материал;
        3.1) Параллельно производится проверка, существует ли необходимая карта
        текстур в исходном файле;
        4.1) Если не существует, создается новый объект карты текстур, который
        ссылается на новый объект текстуры, которая ссылается на новое
        изображение.

        Args:
            gltf (GLTF2): объект редактуируемого 3Д-файла
            material_name (str): название материала, в котором изменяется
            текстура, для его поиска в структуре файла
            texture_info (str): тип карты текстуры: normalTexture,
            baseColorTexture, metallicRoughnessTexture, словом, тот, у кого
            есть параметр index со ссылкой на текстуру
            image (Image): объект изображения. Во всяком случае объект
            изображения создается новый, будет ли он заменять уже существующий
            или займет место в новой текстуре
            submaterial (str | None, optional): На случай, если карта у нас
            baseColorTexture или metallicRoughnessTexture, до них приходится
            добираться через объект pbrMetallicRoughness. Собственно, в этот
            параметр передается либо pbrMetallicRoughness, либо дефолтное
            значение None.

        Returns:
            GLTF2: редактированный объект GLTF2, готовый к конвертации
            изображений и записи в новый файл.
        """

        # Отыскиваем необходимый материал по его имени
        target_materials = tuple(
            material for material in gltf.materials
            if material.name == material_name
        )
        try:
            # Если в файле нет таких материалов, возникнет ошибка.
            assert len(target_materials) != 0
        except AssertionError:
            raise GLBEditorException(
                detail="В редактируемом файле отсутствет материал с именем "
                f"{material_name}, указанным в поступившем запросе",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
            # TODO: Реализовать подобный функционал вместо ошибки.
        # Теоретически не должно быть двух материалов с одинаковыми именами,
        # если это не так, то имеет место коллизия, которую нужно рассмотреть
        # отдельно.
        target_material = target_materials[0]

        # Здесь мы отбираем у полученного материала соответствующий объект
        # карты текстуры, чтобы понять, на какую текстуру она ссылается.
        # Пример:
        # source_texture_map = getattr(
        #     getattr(Material, "pbrMetallicRoughness"),
        #     "baseColorTexture"
        # )
        # вернет нам либо None, если таких объектов в материале нет, а значит
        # нужно добавить текстуру, либо объект класса TextureInfo, в котором
        # будет ссылка на текстуру.
        # "baseColorTexture" и "pbrMetallicRoughess" берутся из тела запроса,
        # т.е. на этом этапе происходит проверка наличия запрашиваемой
        # к изменению текстуры в самом изменяемом файле.
        # Если у нас normalTexture, то submaterial опускается, пример вызова
        # выглядит так:
        # source_texture_map = getattr(Material, "normalTexture")
        source_texture_map = (
            getattr(getattr(target_material, submaterial), texture_info)
            if submaterial
            else getattr(target_material, texture_info)
        )
        if source_texture_map is None:
            # Если заданная в запросе текстура, а точнее карта текстур в материале
            # отсутствует, мы просто создаем все с нуля - карту, текстуру, объект
            # изображения и интегрируем их в файл.
            return self._add_texture_map_to_material(
                gltf, target_material, texture_info, image, submaterial
            )
        else:
            # Если карта соответствующая карта текстур в файле есть, нам нужно
            # проверить две вещи:
            # 1) Есть ли кто-то еще, какая-то карта текстур, которая ссылается
            # на эту же текстуру;
            # 2) Есть ли какая-то еще текстура, которая ссылается на это же
            # изображение
            # Если ответ на какой-либо из вопросов "Да", то мы, не изменяя
            # тип карты текстур, создаем новую текстуру, связанную с новым
            # изображением, а затем подменяем в данном материале индекс
            # текстуры на индекс новой текстуры.
            image_index = gltf.textures[source_texture_map.index].source
            textures_with_repeated_image_indexes = tuple(
                texture
                for texture in gltf.textures
                if texture.source == image_index
            )
            materials_with_repeated_texture_indexes = tuple(
                material
                for material in gltf.materials
                if self._is_texture_used_by_someone_else(
                    material, source_texture_map.index
                )
            )
            if (
                len(textures_with_repeated_image_indexes) > 1
                or len(materials_with_repeated_texture_indexes) > 1
            ):
                return self._change_texture_in_material(
                    gltf, target_material, texture_info, image, submaterial
                )
            else:
                # Если ответ "Нет", то мы можем безболезненно, не создавая
                # новую текстуру и не раздувая общее число текстур в файле,
                # добавить новое изображение и заставить текстуру ссылаться
                # на него, не опасаясь того, что другие материалы, использующие
                # данную текстуру, тоже случайно поменяют изображение.
                # Остается, конечно, проблема, неуникальности материалов,
                # то есть, когда разные элементы состоят из одного материала,
                # и замена текстуры одного материала повлияет сразу на несколько
                # элементов модели, но тут уж ничего, наверное, не поделать.
                return self._add_image_to_texture(
                    gltf, textures_with_repeated_image_indexes[0], image
                )

    @staticmethod
    def _add_image_to_texture(
        gltf: GLTF2, texture_to_change: Texture, image: Image
    ) -> GLTF2:
        """
        Метод, который подменяет ссылку на изображение сразу в текстуре.
        Материалы, карты текстур - все это остается неизменным.
        """
        # Получим индекс текстуры, которую нам нужно изменить.
        # Заодно изменим имя текстуры на необходимое.
        texture_idx = gltf.textures.index(texture_to_change)
        image_name_extension = image.name.rfind(".")
        gltf.textures[texture_idx].name = image.name[:image_name_extension]
        try:
            # Попробуем понять, работали ли мы на предыдущей итерации с данным
            # изображением. Если работали, просто найдем его индекс и заменим
            # ссылку в текстуре
            image_index = gltf.images.index(image)
            gltf.textures[texture_idx].source = image_index
        except ValueError:
            # Если не работали, добавим изображение в список изображений
            # и укажем в текстуре ссылку на новое изображение - последнее
            # в общем списке.
            gltf.images.append(image)
            gltf.textures[texture_idx].source = len(gltf.images) - 1
        return gltf

    @staticmethod
    def _add_texture_map_to_material(
        gltf: GLTF2,
        material: Material,
        texture_name: str,
        image: Image,
        submaterial: str = None,
    ) -> GLTF2:
        """
        Метод для добавления новой карты текстуры целиком в файл.
        """
        # Существующие варианты карты текстур
        textures_map = {
            "pbrMetallicRoughness": PbrMetallicRoughness,
            "normalTexture": NormalMaterialTexture,
        }
        # Новая текстура, которая будет связана с новой картой
        texture = Texture()
        image_name_extension = image.name.rfind(".")
        texture.name = image.name[:image_name_extension]

        try:
            # Попробуем найти, вдруг на предыдущей итерации новое изображение
            # уже было добавлено в файл.
            image_index = gltf.images.index(image)
            # Если находим, используем для текстуры его индекс
            texture.source = image_index
        except ValueError:
            # Если же нет, добавляем изображение в список изображений файла,
            # индекс изображения стандартный - длина списка изображений минус
            # один
            gltf.images.append(image)
            texture.source = len(gltf.images) - 1

        # Добавляем текстуру со ссылкой на изображение в общий список текстур
        gltf.textures.append(texture)

        # Определяем порядковый индекс материала в списке материалов файла
        material_idx = gltf.materials.index(material)
        # Если карта текстур pbrMetallicRoughness, нужно соблюсти вложенность
        # структуры
        if submaterial:
            # Создадим объект TextureInfo - он является общим типом объекта
            # для baseColorTexture и metallicRoughnessTexture
            new_texture_info = TextureInfo()
            # Определим, что ссылается этот объект в качестве текстуры
            # на последнюю добавленную текстуру
            new_texture_info.index = len(gltf.textures) - 1
            # Создадим объект pbrMetallicRoughness, родительский для объектов
            # baseColorTexture и metallicRoughnessTexture, воспользовавшись
            # подготовленным словарем
            new_texture = textures_map[submaterial]()
            # По иерархии снизу вверх привяжем сначала объект TextureInfo
            # к объекту pbrMetallicRoughness, конкретное имя свойства при этом
            # (baseColorTexture или metallicRoughnessTexture) будет также
            # учтено, поскольку данное имя взято из запроса и содержится
            # в переменной texture_name
            setattr(new_texture, texture_name, new_texture_info)
            # А затем уже привяжем карту текстур - объект pbrMetallicRoughness
            # к необходимому материалу из списка материалов в файле.
            setattr(gltf.materials[material_idx], submaterial, new_texture)
        else:
            # Если нужно создать карту текстур типа normalTexture, все гораздо
            # проще.
            # Создаем пустую карту текстур
            new_texture = textures_map[texture_name]()
            # Привязываем к ней последнюю добавленную текстуру
            new_texture.index = len(gltf.textures) - 1
            # Связываем карту текстур с необходимым материалом.
            setattr(gltf.materials[material_idx], texture_name, new_texture)
        return gltf

    @staticmethod
    def _change_texture_in_material(
        gltf: GLTF2,
        material: Material,
        texture_name: str,
        image: Image,
        submaterial: str = None,
    ) -> GLTF2:
        """
        Метод, который добавляет текстуру и подменяет ссылку в материале так,
        чтобы он ссылался на новую текстуру.
        """
        # Во всяком случае нам нужно создать новую текстуру.
        texture = Texture()
        image_name_extension = image.name.rfind(".")
        texture.name = image.name[:image_name_extension]
        try:
            # Попробуем найти, вдруг на предыдущей итерации новое изображение
            # уже было добавлено в файл.
            image_index = gltf.images.index(image)
            # Если находим, используем для текстуры его индекс
            texture.source = image_index
        except ValueError:
            # Если же нет, добавляем изображение в список изображений файла,
            # индекс изображения стандартный - длина списка изображений минус
            # один
            gltf.images.append(image)
            texture.source = len(gltf.images) - 1

        # Добавляем текстуру со ссылкой на изображение в общий список текстур
        gltf.textures.append(texture)

        # Определяем порядковый индекс материала в списке материалов файла
        material_idx = gltf.materials.index(material)
        # Если карта текстур pbrMetallicRoughness, нужно соблюсти вложенность
        # структуры
        if submaterial:
            # Сначала мы получаем доступ к карте текстур pbrMetallicRoughness
            submaterial_obj = getattr(
                gltf.materials[material_idx], submaterial
            )
            # Получаем из нее объект класса TextureInfo - это либо
            # baseColorTexture, либо metallicRoughnessTexture, в любом случае
            # соответствующий атрибут мы получаем из запроса.
            texture_info_obj = getattr(submaterial_obj, texture_name)
            # Подменяем в данном объекте текстуру - теперь он ссылается
            # на последнюю добавленную текстуру в файле.
            texture_info_obj.index = len(gltf.textures) - 1

            # # Произведем сборку в обратном порядке - определим, что объект
            # # TextureInfo связан с картой текстур pbrMetallicRoughness
            # setattr(submaterial_obj, texture_name, texture_info_obj)
            # # А затем определим, что карта текстур pbrMetallicRoughness
            # # связана с соответствующим материалом файла.
            # setattr(gltf.materials[material_idx], submaterial, submaterial_obj)

            # Вещь, о которой я не задумывался, но проверил, и она оказалась
            # верной: getattr() возвращает не копию объекта, она возвращает
            # ссылку на этот объект. Это равносильно обращению напрямую
            # к свойству объекта. Поэтому нет никакого смысла устанавливать
            # вручную значения каких-либо атрибутов - взаимодействуя
            # с результатом работы функции getattr(), мы взаимодействуем
            # со свойствами объекта напрямую.

        else:
            # В случае с картой текстур типа normalTexture все проще и в целом
            # процесс аналогичен и понятен.
            normal_texture_obj = getattr(
                gltf.materials[material_idx], texture_name
            )
            normal_texture_obj.index = len(gltf.textures) - 1
            # setattr(
            #     gltf.materials[material_idx], texture_name, normal_texture_obj
            # )

        return gltf

    @staticmethod
    def _is_texture_used_by_someone_else(material, compared_index):
        pbr_metallic_roughness = getattr(material, "pbrMetallicRoughness")
        pbr_metallic_roughness_exists = isinstance(
            pbr_metallic_roughness, PbrMetallicRoughness
        )

        normal_texture = getattr(material, "normalTexture")
        normal_texture_exists = isinstance(
            normal_texture, NormalMaterialTexture
        )

        if pbr_metallic_roughness_exists:
            base_color_texture = getattr(
                pbr_metallic_roughness, "baseColorTexture"
            )
            base_color_texture_exists = isinstance(
                base_color_texture, TextureInfo
            )

            metallic_roughness_texture = getattr(
                pbr_metallic_roughness, "metallicRoughnessTexture"
            )
            metallic_roughness_texture_exists = isinstance(
                metallic_roughness_texture, TextureInfo
            )
        else:
            base_color_texture_exists = None
            metallic_roughness_texture_exists = None

        if normal_texture_exists:
            return compared_index == normal_texture.index
        if base_color_texture_exists:
            return compared_index == base_color_texture.index
        if metallic_roughness_texture_exists:
            return compared_index == metallic_roughness_texture.index
        return False
