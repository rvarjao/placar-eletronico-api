"""Aplicação publicada do Placar Eletrônico."""


def create_app():
    from .server import app

    return app


def __getattr__(name):
    # O WSGI publicado antes da reorganização usa `from app import app`.
    # A carga tardia preserva esse import sem inicializar o servidor quando
    # os clientes independentes importam apenas app.db_supabase.
    if name == "app":
        return create_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
