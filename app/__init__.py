"""Aplicação publicada do Placar Eletrônico."""


def create_app():
    from .server import app

    return app
