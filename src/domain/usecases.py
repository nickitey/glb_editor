# Модуль с описанием класса, который импортирует repositories и используется
# в качестве внедряемой зависимости.
from src.data.repositories import GLBParamsRepository
from src.domain.entities import PropertiesData


class ChangeParamsUseCase:
    def __init__(self, file_repo: GLBParamsRepository):
        self._file_repo = file_repo()

    async def invoke(self, request_data_object: PropertiesData) -> bool:
        return await self._file_repo.change_parameters(request_data_object)
