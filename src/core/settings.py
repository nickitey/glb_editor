import os
from dataclasses import dataclass, field

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())


@dataclass
class FastAPIAppConfig:
    mount_swagger: bool = os.getenv("APP__MOUNT_SWAGGER")
    mount_redoc: bool = os.getenv("APP__MOUNT_REDOC")


@dataclass
class Settings:
    app: FastAPIAppConfig = field(default_factory=FastAPIAppConfig)


settings = Settings()
