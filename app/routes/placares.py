from flask import Blueprint, abort
from app.services.placar_service import PlacarService

placares_bp = Blueprint("placares", __name__)


@placares_bp.post("/placares")
def criar_placar():
    # TODO alunos: validar JSON, chamar serviço e responder 201.
    abort(501)


@placares_bp.get("/placares/<int:placar_id>")
def buscar_placar(placar_id):
    # TODO alunos: buscar por ID, responder 200 ou 404.
    abort(501)


@placares_bp.patch("/placares/<int:placar_id>")
def atualizar_placar(placar_id):
    # TODO alunos: autorizar, validar, atualizar e responder 200.
    abort(501)
