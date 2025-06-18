# glb-editor

## Редактор GLB-файлов

## Подготовка к запуску

Перед запуском приложения необходимо создать конфигурацию приложения - файл `.env` в корневой директории проекта - и наполнить его переменными окружения по образцу файла [`.env.example`](./.env.example). Можно просто переименовать файл [`.env.example`](./.env.example) в `.env`, если никакие настройки менять не собираетесь.

Значения настроек:

- `UVICORN__PORT` - порт хоста, на который будут поступать запросы, которые необходимо передать внутрь контейнера для работы веб-приложения;
- `MOUNT_SWAGGER` - необходима ли автогенерация интерактивной документации [Swagger](https://thecode.media/chto-takoe-swagger-i-kak-on-oblegchaet-rabotu-s-api/). Допустимые значения: `True/False`[^1]. Если `True`, после запуска приложения по адресу [/docs](http://localhost:9596/docs) будет доступа схема API;
- `MOUNT_REDOC` - необходима ли автогенерация интерактивной документации [Redoc](https://aappss.ru/b/rest-api/?ysclid=m4lpmbx55332788192). Допустимые значения: `True/False`[^1]. Если `True`, после запуска приложения по адресу [/redoc](http://localhost:9596/redoc) будет доступа схема API.

## Запуск

```bash
    ./launch.sh
```

## Использование

Сервис представляет веб-приложение для редактирования GLB-файлов.

Редактируются файлы, находящиеся на том же устройстве (ПК, сервер), на котором запущено приложение. 

Функционал приложения доступен посредством HTTP-запросов по следующим эндпоинтам:

- [/parameters](http://localhost:9596/parameters). Принимаются POST-запросы, `Content-Type`: `application/json`.

Структура тела запроса:

```JSON
{
    "source_filepath": <string>,
    "result_filepath": <string>,
    "materials": <array>
}
```

Обязательные поля в теле запроса: `source_filepath`, `result_filepath` и `materials`.

`source_filepath` представляет собой путь к исходному (редактируемому) файлу. Тип данных - строка (`string`).

`result_filepath` - путь к директории для готовых (отредактированных) файлов. Если директория не существует, она будет создана.

`materials` - список (массив) объектов, структурно соответствующий [спецификации GLTF/GLB](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#reference-material).

В процессе обработки запроса в редактируемом файле по имени отбираются материалы, json-репрезентация которых содержится в теле запроса, после чего все одноименные параметры исходного файла заменяются таковыми из тела запроса. Если в теле запроса содержится какой-либо параметр материала, отсутствующий в исходном файле, он добавляется в файл.

Образец тела запроса:

```json
{
    "source_filepath": "/usr/source_files/Stul.glb",
    "result_filepath": "/opt/results/",
    "materials": [
        {
      "pbrMetallicRoughness": {
        "baseColorFactor": [
          1,
          1,
          0,
          0.5
        ],
        "metallicFactor": 0,
        "roughnessFactor": 0.9717159867286682
      },
      "name": "Material_Stand"
    },
    {
      "pbrMetallicRoughness": {
        "baseColorFactor": [
          1,
          0,
          0,
          1
        ],
        "metallicFactor": 0,
        "roughnessFactor": 0.25
      },
      "name": "Material_Base"
    },
    {
      "pbrMetallicRoughness": {
        "baseColorFactor": [
          1,
          0,
          1,
          1
        ],
        "metallicFactor": 0,
        "roughnessFactor": 0.3500000238418579
      },
      "name": "Material_Tiles"
    }
  ]
}
```

После редактирования расширение файла не изменяется, к исходному имени файла добавляется последовательность цифр для избежания перезаписи уже существующего файла в указанной директории.

Веб-приложение возвращает ответ:

```JSON
{
    "status": "Готово",
    "filename": "/opt/results/Stul_085058.glb"
}
```

- [/textures](http://localhost:9596/textures). Принимаются POST-запросы, `Content-Type`: `application/json`.

Структура тела запроса:

```JSON
    "source_glbfilepath": <str>,
    "result_filepath": <str>
    "files": [
      {
        "texturefilepath": <str>, 
        "materials": <array>
      }
    ]
```

Параметры `source_glbfilepath` и `result_filepath` аналогичны `source_filepath` и `result_filepath` из предыдущего пункта соответственно, `files` - массив характеристик изменяемых текстур, где `texturefilepath` - имя нового файла текстуры, который подлежит вставке в редактируемый файл, `materials` снова повторяет таковой из предыдущего пункта.

В процессе обработки запроса в редактируемом файле по имени отбираются материалы, json-репрезентация которых содержится в теле запроса. После этого анализируется тип текстуры: `pbrMetallicRoughness`, `normalTexture` и вычисляется, на какие непосредственно объекты текстур ссылаются указанные материалы. После чего изображение, на которое ссылается текстура, подменяется на новое, полученное из файла, имя которого указано в запросе.

Образец тела запроса:

```JSON
{
    "source_glbfilepath": "/var/resources/AmoebaBabylonDissasemble.glb",
    "result_filepath": "/tmp",
    "files": [
      {
      "texturefilepath": "/one/texture/dir/texturefile.png",
      "materials": [
          {
            "name": "GLB Nucleus 01",
            "pbrMetallicRoughness": {
              "baseColorTexture": {}
              }
          }
        ]
      },
      {
        "texturefilepath": "/some/other/dir/woodrat-xl.png",
        "materials": [
          {
            "normalTexture": {},
            "pbrMetallicRoughness": {
              "baseColorTexture": {}
              },
            "name": "GLB Water 1st"
          }
        ]
      }
    ]
}
```

Если в запросе будет карта текстур, отсутствующая в изменяемом файле, карта из запроса будет добавлена в файл, ей будет сопоставлена вновь созданная текстура, ссылающаяся на изоражение, путь к которому указан в запросе.

В случае успешной работы веб-приложение возвращает ответ:

```JSON
{
    "status": "Готово",
    "filename": "/tmp/AmoebaBabylonDissasemble_085058.glb"
}
```

После редактирования расширение файла не изменяется, к исходному имени файла добавляется последовательность цифр для избежания перезаписи уже существующего файла в указанной директории.


[^1]: Написание имеет значение, `true/false` строчными буквами вызовет ошибку.
