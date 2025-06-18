import os
from dataclasses import dataclass, field

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())


@dataclass
class FastAPIAppConfig:
    mount_swagger: bool = os.getenv("MOUNT_SWAGGER")
    mount_redoc: bool = os.getenv("MOUNT_REDOC")


@dataclass
class UvicornConfig:
    port: int = int(os.getenv("UVICORN_PORT"))
    workers: int = int(os.getenv("UVICORN_WORKERS"))


@dataclass
class Settings:
    app: FastAPIAppConfig = field(default_factory=FastAPIAppConfig)
    uvicorn: UvicornConfig = field(default_factory=UvicornConfig)


settings = Settings()
