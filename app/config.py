import os


class Config:
    # TODO alunos: validar variáveis de ambiente.
    DATABASE_URL = os.getenv("DATABASE_URL")
