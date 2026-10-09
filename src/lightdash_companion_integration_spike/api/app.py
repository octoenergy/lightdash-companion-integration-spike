import contextlib
import os
import pathlib
import sqlite3
from collections.abc import AsyncIterator

import fastapi
from fastapi import staticfiles

from lightdash_companion_integration_spike import config
from lightdash_companion_integration_spike import logging_setup
from lightdash_companion_integration_spike.api import routes
from lightdash_companion_integration_spike.storage import sqlite

DATABASE_PATH = "spike.sqlite3"
WEB_DIST = pathlib.Path(__file__).parents[3] / "web" / "dist"


def create_app(*, settings: config.Settings, connection: sqlite3.Connection) -> fastapi.FastAPI:
    @contextlib.asynccontextmanager
    async def lifespan(app: fastapi.FastAPI) -> AsyncIterator[None]:
        # PydanticAI's OpenAI provider reads the key from the environment.
        os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key or "")
        logging_setup.configure(level=settings.log_level)
        yield

    app = fastapi.FastAPI(lifespan=lifespan)
    app.state.settings = settings
    app.state.connection = connection
    app.include_router(routes.router)
    if WEB_DIST.exists():
        app.mount("/", staticfiles.StaticFiles(directory=WEB_DIST, html=True), name="web")
    return app


def create_default_app() -> fastapi.FastAPI:
    return create_app(
        settings=config.load_settings(), connection=sqlite.connect(path=DATABASE_PATH)
    )
