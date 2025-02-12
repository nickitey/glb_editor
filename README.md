# glb-editor

## Редактор GLB-файлов

## Подготовка к запуску

Перед запуском приложения необходимо создать конфигурацию приложения - файл `.env` в корневой директории проекта - и наполнить его переменными окружения по образцу файла [`.env.example`](./.env.example). Можно просто переименовать файл [`.env.example`](./.env.example) в `.env`, если никакие настройки менять не собираетесь.

Значения настроек:

- `UVICORN__PORT` - порт хоста, на который будут поступать запросы, которые необходимо передать внутрь контейнера для работы веб-приложения;
- `APP__MOUNT_SWAGGER` - необходима ли автогенерация интерактивной документации [Swagger](https://thecode.media/chto-takoe-swagger-i-kak-on-oblegchaet-rabotu-s-api/). Допустимые значения: `True/False`[^1]. Если `True`, после запуска приложения по адресу [/docs](http://localhost:9191/docs) будет доступа схема API;
- `APP__MOUNT_REDOC` - необходима ли автогенерация интерактивной документации [Redoc](https://aappss.ru/b/rest-api/?ysclid=m4lpmbx55332788192). Допустимые значения: `True/False`[^1]. Если `True`, после запуска приложения по адресу [/redoc](http://localhost:9191/redoc) будет доступа схема API.

О настройках `SOURCE_DIR`, `RESULTS_DIR`, `TEXTURES_DIR` будет сказано дополнительно.

## Запуск

 Существует два варианта запуска приложения:

1) Запустить скрипт `launch.sh`;
2) В терминале/командной строке, находясь в директории проекта, запустить команду

```bash
    docker compose up
```

Оба варианта в целом равнозначны и запускают Docker-контейнер с веб-приложением.

Запуск приложения с помощью утилиты `Docker Compose` является предпочтительным в случае, если поверх бэкенда будет установлен фронтенд-компонент, который можно будет удобно встроить в собственном контейнере для организации сети контейнеров.

## Использование

Сервис представляет веб-приложение для редактирования GLB-файлов.

Редактируются файлы, находящиеся на том же устройстве (ПК, сервер), на котором запущено приложение.

Для этого в [`.env.example`](./.env.example) указывается переменная окружения - `SOURCE_DIR`, которая содержит абсолютный путь к директории, в которой должен находиться исходный файл, подлежащий редактированию. 

Выбор в пользу статической директории для исходных файлов вместо указания полного пути к редактируемому файлу в каждом случае использования обусловлен тем, что в различных операционных системах по-разному реализуется разграничение полномочий доступа пользователя (и запускаемых им приложений) к ресурсам компьютера, в связи с чем может возникнуть ситуация, когда указанный файл недоступен по причине отсутствия тех или иных прав пользователя, от имени которого запущен редактор.

В свою очередь указание статической папки на хосте/сервере позволяет определенным образом настроить права доступа к ней и избежать неожиданных ситуаций в работе приложения. То же касается и директорий для текстур и уже отредактированных файлов. 

Функционал приложения доступен посредством HTTP-запросов по следующим эндпоинтам:

- [/parameters](http://localhost:9596/parameters). Принимаются POST-запросы, `Content-Type`: `application/json`.

Структура тела запроса:

```JSON
{
    "filepath": <string>,
    "materials": <array>
}
```

Обязательные поля в теле запроса: `filepath` и `materials`.

`filepath` представляет собой имя файла, находящегося в директории `SOURCE_DIR`. Тип данных - строка (`string`)

`materials` - список (массив) объектов, структурно соответствующий [спецификации GLTF/GLB](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#reference-material).

В процессе обработки запроса в редактируемом файле по имени отбираются материалы, json-репрезентация которых содержится в теле запроса, после чего все одноименные параметры исходного файла заменяются таковыми из тела запроса. Если в теле запроса содержится какой-либо параметр материала, отсутствующий в исходном файле, он добавляется в файл.

Образец тела запроса:

```json
{
    "filepath": "Stul.glb",
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

После редактирования измененный файл сохраняется в директории `RESULTS_DIR`. Расширение файла не изменяется, к исходному имени файла добавляется последовательность цифр для избежания перезаписи уже существующего файла в указанной директории.

Веб-приложение возвращает ответ:

```JSON
{
    "status": "Готово",
    "filename": "Stul_085058.glb"
}
```

- [/textures](http://localhost:9596/textures). Принимаются POST-запросы, `Content-Type`: `application/json`.

Структура тела запроса:

```JSON
    "glbfilepath": <str>,
    "files": [
      {
        "texturefilepath": <str>, 
        "materials": <array>
      }
    ]
```

Параметр `glbfilepath` аналогичен `filepath` из предыдущего пункта, `files` - массив характеристик изменяемых текстур, где `texturefilepath` - имя нового файла текстуры, который подлежит вставке в редактируемый файл и который уже находится в директории `TEXTURES_DIR`, `materials` снова повторяет таковой из предыдущего пункта.

В процессе обработки запроса в редактируемом файле по имени отбираются материалы, json-репрезентация которых содержится в теле запроса. После этого анализируется тип текстуры: `pbrMetallicRoughness`, `normalTexture` и вычисляется, на какие непосредственно объекты текстур ссылаются указанные материалы. После чего изображение, на которое ссылается текстура, подменяется на новое, полученное из файла, имя которого указано в запросе.

Образец тела запроса:

```JSON
{
    "glbfilepath": "AmoebaBabylonDissasemble.glb",
    "files": [
      {
      "texturefilepath": "volcano.png",
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
        "texturefilepath": "loo.png",
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

**NB!**: попытка добавить текстуру, отсутствующую в файле, вызовет ошибку. Это касается как попытки добавить новый материал, так и случая, когда в запросе указан несоответствующий тип текстуры.

Пример: допустим в файле `AmoebaBabylonDissasemble.gltf` существует материал с параметром `"name": "GLB Nucleus 01"`, который имеет такую структуру:

```json
{
  "pbrMetallicRoughness": {
    "baseColorTexture": {
      "index": 0
    },
    "metallicFactor": 0,
    "roughnessFactor": 0.5
  },
  "name": "GLB Nucleus 01",
  "extensions": {
    "KHR_materials_ior": {}
  }
}
```

В представленной структуре видно, что данный материал относится к типу `pbrMetallicRoughness`, за текстуры в котором отвечает параметр `baseColorTexture`.

Попытка изменить в данном материале параметр `normalTexture`, т.е. запрос вида:

```json
{
    "glbfilepath": "AmoebaBabylonDissasemble.glb",
    "files": [
      {
      "texturefilepath": "volcano.png",
      "materials": [
          {
            "name": "GLB Nucleus 01",
            "normalTexture": {}
          }]
      },
      ...
    ]
}
```
вызовет ошибку, поскольку текстуры вида `normalTexture` в нем нет.

В случае успешной работы веб-приложение возвращает ответ:

```JSON
{
    "status": "Готово",
    "filename": "AmoebaBabylonDissasemble_085058.glb"
}
```

После редактирования измененный файл сохраняется в директории `RESULTS_DIR`. Расширение файла не изменяется, к исходному имени файла добавляется последовательность цифр для избежания перезаписи уже существующего файла в указанной директории.


[^1]: Написание имеет значение, `true/false` строчными буквами вызовет ошибку.
