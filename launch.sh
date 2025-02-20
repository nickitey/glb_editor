#!/bin/sh
export $(grep -v '^#' .env | xargs -d '\n')
echo "$(date +%H:%M:%S\ %d.%m.%Y): Приступаю к сборке образа веб-сервера"
docker build -t glb_editor-glb_editor -f Dockerfile .
echo "$(date +%H:%M:%S\ %d.%m.%Y): Сборка образа веб-сервера закончена"
echo "$(date +%H:%M:%S\ %d.%m.%Y): Запускаю контейнер с сервером. Сервер слушает запросы, поступающие на порт $UVICORN_PORT хоста"
docker run --rm \
	--name glb_editor \
    -v $PWD/:/usr/apps/glb_editor/ \
	-v $SOURCE_DIR:/usr/glb/source \
    -v $RESULTS_DIR:/usr/glb/results \
    -v $TEXTURES_DIR:/usr/glb/textures \
    -p $UVICORN_PORT:9000 \
	--env-file .env \
	glb_editor-glb_editor \
	python -m uvicorn src:app --host 0.0.0.0 --port 9000 --workers $UVICORN_WORKERS
