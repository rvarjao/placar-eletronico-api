from flask import Flask
from app.config import Config
from app.routes.placares import placares_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.register_blueprint(placares_bp, url_prefix="/api")
    # TODO alunos: extensões, banco e tratamento de erros.
    return app
