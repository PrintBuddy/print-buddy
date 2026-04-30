from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.exc import OperationalError, InterfaceError
from fastapi.middleware.cors import CORSMiddleware


from .core.config import settings
from .core.scheduler import scheduler
from .core.logger import logger
from .api import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()

    yield

    scheduler.shutdown()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[settings.URL, "127.0.0.1", "localhost", "10.0.10.3", "*.local", "backend"]
)


origins = [
    "*"
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,        
    allow_credentials=True,
    allow_methods=["*"],          
    allow_headers=["*"],          
)



@app.middleware("http")
async def db_error_handler(request: Request, call_next):
    try:
        return await call_next(request)
    except (OperationalError, InterfaceError) as e:
        logger.error("Database connection error")

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Database connection error"}
        )

app.include_router(router)
