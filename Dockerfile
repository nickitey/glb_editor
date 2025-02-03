FROM python:3.12-slim

WORKDIR /usr/apps/glb_editor

COPY requirements.txt requirements.txt

RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .