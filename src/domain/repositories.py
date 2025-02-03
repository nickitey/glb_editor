import abc

from src.domain.entities import PropertiesData


# Модуль абстрактных классов, переопределенных в data/repositories
class IGLBParamsRepository(abc.ABC):
    async def change_parameters(data: PropertiesData): ...
