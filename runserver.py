import uvicorn
import uvicorn.config
from src import settings

uvicorn.config.LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s - %(levelname)s - %(message)s"
uvicorn.config.LOGGING_CONFIG["formatters"]["access"]["fmt"] = "%(asctime)s - %(levelname)s - %(client_addr)s - '%(request_line)s' %(status_code)s"


if __name__ == "__main__":
    uvicorn.run(
        app="src:app",
        port=settings.uvicorn.port,
        workers=settings.uvicorn.workers,
    )
