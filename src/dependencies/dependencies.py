# Здесь находится класс для создания зависимости, пробрасываемой в обработчик
# запросов (Dependency Injection)

from src.data.repositories import GLBParamsRepository
from src.domain.usecases import ChangeParamsUseCase


class Container:
    params_editor_usecase = ChangeParamsUseCase(GLBParamsRepository)
