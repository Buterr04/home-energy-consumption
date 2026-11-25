from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import (
    APIError,
    api_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from app.routers import (
    admin,
    ai,
    appliances,
    auth,
    consumption,
    households,
    reports,
)
from app.services.model import model_registry

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    model_registry.load(settings.model_path)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Household electricity consumption analysis API. "
            "The service loads a pretrained model and performs inference only."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(
        RequestValidationError, validation_error_handler
    )
    app.add_exception_handler(Exception, unhandled_error_handler)

    for router in (
        auth.router,
        households.router,
        appliances.router,
        consumption.router,
        ai.router,
        reports.router,
        admin.router,
    ):
        app.include_router(router, prefix=settings.api_prefix)

    return app


app = create_app()
