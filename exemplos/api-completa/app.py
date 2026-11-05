import hmac
import json
import os
import subprocess
import sqlite3
from pathlib import Path
from threading import Lock
from time import perf_counter

from flask import Flask, g, jsonify, request

from admin_panel import admin_bp, autenticar_token, inicializar_banco, registrar_requisicao

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "troque-esta-chave-em-producao")
app.register_blueprint(admin_bp)
inicializar_banco()
ARQUIVO = Path(__file__).with_name("placares.json")
LOCK = Lock()
API_KEY = os.getenv("x-api-key", "chave-aula-123")  # Somente para aula local
DEPLOY_TOKEN = os.getenv("DEPLOY_TOKEN", "")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CAMPOS = ("nome_equipe_a", "nome_equipe_b", "modalidade")
STATUS = {"aguardando", "em_andamento", "encerrado"}

def ler():
    placares = json.loads(ARQUIVO.read_text(encoding="utf-8")) if ARQUIVO.exists() else []
    for placar in placares:
        placar.setdefault("tempo_partida", 0)
    return placares

def salvar(placares):
    temporario = ARQUIVO.with_suffix(".tmp")
    temporario.write_text(json.dumps(placares, ensure_ascii=False, indent=2), encoding="utf-8")
    temporario.replace(ARQUIVO)

def erro(mensagem, status):
    return jsonify({"erro": mensagem}), status

def localizar(placares, id):
    return next((p for p in placares if p["id"] == id), None)

def validar_equipes(dados):
    if not isinstance(dados, dict):
        return "Envie um objeto JSON"
    if not all(isinstance(dados.get(c), str) and dados[c].strip() for c in CAMPOS):
        return "Informe nome_equipe_a, nome_equipe_b e modalidade como textos não vazios"
    return None

def pontos_validos(dados):
    return all(isinstance(dados.get(c), int) and not isinstance(dados[c], bool) and dados[c] >= 0 for c in ("pontos_a", "pontos_b"))

def tempo_valido(dados):
    tempo = dados.get("tempo_partida")
    return isinstance(tempo, int) and not isinstance(tempo, bool) and tempo >= 0

@app.before_request
def autenticar_requisicao():
    g.inicio_requisicao = perf_counter()
    g.grupo_api_id = None

    if not request.path.startswith("/api/"):
        return None

    autorizacao = request.headers.get("Authorization", "")
    token = autorizacao.removeprefix("Bearer ").strip() if autorizacao.startswith("Bearer ") else ""
    grupo = autenticar_token(token)

    if grupo is not None:
        g.grupo_api_id = grupo["id"]
        g.grupo_api_nome = grupo["nome"]
        return None

    chave_legada = request.headers.get("X-API-Key", "")
    if chave_legada and hmac.compare_digest(chave_legada, API_KEY):
        return None

    return erro("Token do grupo ausente ou inválido", 401)


@app.after_request
def monitorar_requisicao(resposta):
    if request.path.startswith("/api/"):
        inicio = getattr(g, "inicio_requisicao", perf_counter())
        duracao_ms = max(0, round((perf_counter() - inicio) * 1000))
        try:
            registrar_requisicao(
                getattr(g, "grupo_api_id", None),
                request.method,
                request.path,
                resposta.status_code,
                duracao_ms,
            )
        except sqlite3.Error:
            app.logger.exception("Não foi possível registrar a requisição da API")
    return resposta

@app.post("/internal/deploy")
def deploy():
    token_recebido = request.headers.get("X-Deploy-Token", "")

    if not DEPLOY_TOKEN:
        return erro("DEPLOY_TOKEN não configurado", 503)

    if not hmac.compare_digest(token_recebido, DEPLOY_TOKEN):
        return erro("Token de deploy inválido", 401)

    resultado = subprocess.run(
        ["git", "pull", "--ff-only", "origin", "main"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    saida = "\n".join(
        parte
        for parte in (resultado.stdout.strip(), resultado.stderr.strip())
        if parte
    )

    if resultado.returncode != 0:
        return jsonify({"erro": "Falha ao atualizar o repositório", "saida": saida}), 500

    return jsonify({"status": "updated", "saida": saida}), 200


@app.get("/api/placares")
def listar():
    with LOCK:
        return jsonify(ler()), 200

@app.get("/api/placares/<int:id>")
def consultar(id):
    with LOCK:
        placar = localizar(ler(), id)
    return (jsonify(placar), 200) if placar else erro("Placar não encontrado", 404)

@app.post("/api/placares/criar")
def criar():
    dados = request.get_json(silent=True)
    mensagem = validar_equipes(dados)
    if mensagem:
        return erro(mensagem, 400)
    with LOCK:
        placares = ler()
        id = max((p["id"] for p in placares), default=0) + 1
        placar = {"id": id, **{c: dados[c].strip() for c in CAMPOS}, "status": "aguardando", "pontos_a": 0, "pontos_b": 0, "tempo_partida": 0}
        placares.append(placar)
        salvar(placares)
    return jsonify(placar), 201, {"Location": f"/api/placares/{id}"}

@app.put("/api/placares/<int:id>")
def substituir(id):
    dados = request.get_json(silent=True)
    mensagem = validar_equipes(dados)
    if mensagem:
        return erro(mensagem, 400)
    if not pontos_validos(dados) or not tempo_valido(dados) or dados.get("status") not in STATUS:
        return erro("Informe status válido, pontos_a/pontos_b e tempo_partida como inteiros não negativos", 400)
    with LOCK:
        placares = ler()
        atual = localizar(placares, id)
        if atual is None:
            return erro("Placar não encontrado", 404)
        novo = {"id": id, **{c: dados[c].strip() for c in CAMPOS}, "status": dados["status"], "pontos_a": dados["pontos_a"], "pontos_b": dados["pontos_b"], "tempo_partida": dados["tempo_partida"]}
        placares[placares.index(atual)] = novo
        salvar(placares)
    return jsonify(novo), 200

@app.patch("/api/placares/<int:id>")
def alterar(id):
    dados = request.get_json(silent=True)
    permitidos = {"pontos_a", "pontos_b", "status", "tempo_partida"}
    if not isinstance(dados, dict) or not dados or set(dados) - permitidos:
        return erro("Envie apenas pontos_a, pontos_b, status e/ou tempo_partida", 400)
    for campo in ("pontos_a", "pontos_b"):
        if campo in dados and (not isinstance(dados[campo], int) or isinstance(dados[campo], bool) or dados[campo] < 0):
            return erro(f"{campo} deve ser inteiro não negativo", 400)
    if "status" in dados and dados["status"] not in STATUS:
        return erro("Status inválido", 400)
    if "tempo_partida" in dados and not tempo_valido(dados):
        return erro("tempo_partida deve ser inteiro não negativo", 400)
    with LOCK:
        placares = ler()
        placar = localizar(placares, id)
        if placar is None:
            return erro("Placar não encontrado", 404)
        placar.update(dados)
        salvar(placares)
    return jsonify(placar), 200

@app.delete("/api/placares/<int:id>")
def excluir(id):
    with LOCK:
        placares = ler()
        placar = localizar(placares, id)
        if placar is None:
            return erro("Placar não encontrado", 404)
        placares.remove(placar)
        salvar(placares)
    return "", 204

if __name__ == "__main__":
    app.run(debug=True)
