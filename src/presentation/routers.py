import json

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from dacite import from_dict

from src.dependencies.dependencies import Container
from src.domain.entities import PropertiesData, TexturesData
from src.domain.usecases import ChangeParamsUseCase, ChangeTexturesUseCase
from src.presentation.requests import (MaterialsRequestModel,
                                       TexturesRequestModel)

router = APIRouter(prefix="/glbeditor", tags=["Changing GLB-file parameters"])


@router.post("/parameters")
async def change_file_params(
    request: Request, usecase: ChangeParamsUseCase = Depends(Container)
):
    # Есть два варианта, как обрабатывать тело входящего запроса:
    # с валидацией и без.
    # Без валидации проще - но риск подорваться на мине крайне велик.
    # Делается это примерно вот так:
    # Поскольку фреймворк асинхронный напрочь, тело запроса получается
    # как в aiohttp - через корутину.
    # res = await request.body()
    # Полученное тело запроса - бинарный контент, который нужно декодировать.
    # decoded = res.decode()
    # В результате получаем декодированную строку - JSON.
    # Его можно десериализовать в python-объект - словарь.
    # deserialized = json.loads(decoded)
    # print(type(deserialized))  # <class 'dict'>
    # pprint(deserialized)
    # {'name': 'Material_Tiles',
    # 'pbrMetallicRoughness': {'baseColorFactor': [0.5487127836871236,
    #                                           0.24312534162534125,
    #                                           0.9067794799804687,
    #                                           1],
    #                       'metallicFactor': 0,
    #                       'roughnessFactor': 0.3500000238418579}}
    # Минус такого решения очевиден - черт его знает, что нам в запросе придет,
    # как на это реагироать и не сломает ли данный запрос нам логику всего
    # приложения.

    # А вот для валидации нужно писать модели. И есть вопросики, как их писать,
    # а точнее - гарантировано ли, что у нас будут действительно запросы
    # соответствовать моделям?

    # Другая неочевидная проблема использования моделей для валидации выяснилась
    # в процессе разработки.
    # Для того, чтобы модели были универсальными, мы должны в них прописать
    # все возможные параметры, указав, что они могут быть опциональными.
    # "Быть опциональными" - это быть всегда, но, если в теле запроса такого
    # поля/параметра нет, то модель ему устанавливает значение None.
    # Например:

    # class Foo(BaseModel):
    #     a: Optional[int] = None
    #     b: Optional[str] = None

    # Модель Foo говорит нам следующее: я могу валидировать запросы следующего
    # вида:
    # {
    #     "a": 3,
    #     "b": "hello"
    # },
    # {
    #     "a": 100
    # },
    # {
    #     "b": "oh, hi"
    # }
    # Все три такие запроса будут валидными. Но! После валидации у нас на руках
    # (то есть, в обработчике запросов) *всегда* будет объект с ДВУМЯ атрибутами.
    # Просто отсутствующий в запросе атрибут будет заполнен None:
    # foo.a = 3, foo.b = "hello,
    # foo.a = 100, foo.b = None,
    # foo.a = None, foo.b = "oh, hi"

    # И вот здесь уже другая проблема: нам приходят только изменения, которые
    # необходимо внести в имеющийся файл. И при применении изменений к файлу
    # может случиться так, что мы своими Foo.attribute = None случайно заменим
    # аналогичный атрибут File.attribute, у которого будет какое-то другое
    # значение.
    # Мы можем, конечно, фильтровать и, например, не применять изменения,
    # значения которых None. Но как мы можем гарантировать, что изменение
    # значения на None не является желаемым результатом?
    # Пока решение достаточно... топорное видится так: мы принимаем сырой
    # JSON, десериализуем его и в качестве валидации пытаемся создать
    # из него объект класса Material из библиотеки pygltflib. Или, что проще,
    # используя написанные классы-модели, провалидировать ими. Это застрахует
    # нас от ситуаций, когда в запросе переданы какие-то параметры, которые
    # есть в общем классе Material и в спецификации, но которые мы не готовы
    # обрабатывать по каким-то причинам.
    # Если у нас это получается, значит структурно и по типам ожидаемых данных
    # поступивший запрос соответствует спецификации GLB/GLTF, а следовательно
    # мы можем создавать изменения и применять их к файлу.
    # Минус этого подхода один, но существенный: если мы будем использовать
    # в качестве изменений сразу объект класса Material, то мы столкнемся
    # с той же проблемой, что и при валидации данных: у класса Material есть
    # значения атрибутов по умолчанию, и в результате созданный объект будет
    # содержать часть атрибутом из запроса, а часть - значения по умолчанию,
    # причем у изменяемого файла эти атрибуты, которые созданы по умолчанию,
    # могут быть совершенно другие.
    # Поэтому здесь в несколько ступеней будут происходить изменения файлов:
    # 1) мы делаем словарь из тела запроса: какие параметры нужно изменить;
    # 2) мы делаем словарь из необходимых параметров исходного файла;
    # 3) производим слияние словарей таким образом, что в исходном изменяются
    # только те значения, которые есть в словаре изменений;
    # 4) на основе датаклассов из pygltflib мы делаем объект параметров для
    # итогового файла.
    # Опять же, нужно учитывать, что в итоговом файле из-за того, что датклассы
    # универсальны, появятся некоторые параметры со значениями по умолчанию,
    # если их там не было, с другой стороны, параметры со значением None сильно
    # не раздуют размер итогового файла, к тому же библиотека основана
    # на спецификации GLTF, а значит гарантируется полное соответствие стандарту
    # и работоспособность со всеми программными продуктами, которые тоже его
    # используют.

    request_binary_data = await request.body()
    request_data = json.loads(request_binary_data.decode())

    try:
        _ = MaterialsRequestModel.model_validate(request_data)
    except ValidationError as e:
        return JSONResponse(
            {"description": f"Ошибка валидации тела запроса: {e}"},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    else:
        _ = None
        data_object = PropertiesData(
            filepath=request_data["filepath"],
            materials=request_data["materials"],
        )
        result = await usecase.params_editor_usecase.invoke(data_object)

        return JSONResponse(result, status.HTTP_201_CREATED)


@router.post("/textures")
async def change_file_textures(
    request: Request, usecase: ChangeTexturesUseCase = Depends(Container)
):
    request_binary_data = await request.body()
    request_data = json.loads(request_binary_data.decode())

    try:
        _ = TexturesRequestModel.model_validate(request_data)
    except ValidationError as e:
        return JSONResponse(
            {"description": f"Ошибка валидации тела запроса: {e}"},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    else:
        _ = None
        data_object = from_dict(TexturesData, request_data)
        result = await usecase.textures_editor_usecase.invoke(data_object)

        return JSONResponse(result, status.HTTP_201_CREATED)
