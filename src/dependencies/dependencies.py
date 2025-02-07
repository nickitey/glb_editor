# Здесь находится класс для создания зависимости, пробрасываемой в обработчик
# запросов (Dependency Injection)

from src.data.repositories import GLBParamsRepository, GLBTexturesRepository
from src.domain.usecases import ChangeParamsUseCase, ChangeTexturesUseCase


class Container:
    params_editor_usecase = ChangeParamsUseCase(GLBParamsRepository)
    textures_editor_usecase = ChangeTexturesUseCase(GLBTexturesRepository)
