from pathlib import Path

from flask import Flask

from .routes import register_routes


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=str(PROJECT_ROOT / "static"),
        template_folder=str(PROJECT_ROOT / "templates"),
    )
    register_routes(app)
    return app
