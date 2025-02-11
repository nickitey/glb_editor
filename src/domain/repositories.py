import abc

from src.domain.entities import PropertiesData, TexturesData


# Модуль абстрактных классов, переопределенных в data/repositories
class IGLBParamsRepository(abc.ABC):
    async def change_parameters(self, data: PropertiesData): ...


class IGLBTexturesRepository(abc.ABC):
    async def change_textures(self, data: TexturesData): ...
