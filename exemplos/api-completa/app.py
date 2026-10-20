import json
import os
from pathlib import Path
from threading import Lock
from flask import Flask, jsonify, request

app = Flask(__name__)
ARQUIVO = Path(__file__).with_name("placares.json")
LOCK = Lock()
API_KEY = os.getenv("x-api-key", "chave-aula-123")  # Somente para aula local
CAMPOS = ("nome_equipe_a", "nome_equipe_b", "modalidade")
STATUS = {"aguardando", "em_andamento", "encerrado"}

def ler():
    return json.loads(ARQUIVO.read_text(encoding="utf-8")) if ARQUIVO.exists() else []

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

@app.before_request
def proteger_escrita():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.headers.get("X-API-Key") != API_KEY:
        return erro("API Key ausente ou inválida", 401)

@app.get("/api/placares")
def listar():
    with LOCK:
        return jsonify(ler()), 200

@app.get("/api/placares/<int:id>")
def consultar(id):
    with LOCK:
        placar = localizar(ler(), id)
    return (jsonify(placar), 200) if placar else erro("Placar não encontrado", 404)

@app.post("/api/placares")
def criar():
    dados = request.get_json(silent=True)
    mensagem = validar_equipes(dados)
    if mensagem:
        return erro(mensagem, 400)
    with LOCK:
        placares = ler()
        id = max((p["id"] for p in placares), default=0) + 1
        placar = {"id": id, **{c: dados[c].strip() for c in CAMPOS}, "status": "aguardando", "pontos_a": 0, "pontos_b": 0}
        placares.append(placar)
        salvar(placares)
    return jsonify(placar), 201, {"Location": f"/api/placares/{id}"}

@app.put("/api/placares/<int:id>")
def substituir(id):
    dados = request.get_json(silent=True)
    mensagem = validar_equipes(dados)
    if mensagem:
        return erro(mensagem, 400)
    if not pontos_validos(dados) or dados.get("status") not in STATUS:
        return erro("Informe status válido e pontos_a/pontos_b inteiros não negativos", 400)
    with LOCK:
        placares = ler()
        atual = localizar(placares, id)
        if atual is None:
            return erro("Placar não encontrado", 404)
        novo = {"id": id, **{c: dados[c].strip() for c in CAMPOS}, "status": dados["status"], "pontos_a": dados["pontos_a"], "pontos_b": dados["pontos_b"]}
        placares[placares.index(atual)] = novo
        salvar(placares)
    return jsonify(novo), 200

@app.patch("/api/placares/<int:id>")
def alterar(id):
    dados = request.get_json(silent=True)
    permitidos = {"pontos_a", "pontos_b", "status"}
    if not isinstance(dados, dict) or not dados or set(dados) - permitidos:
        return erro("Envie apenas pontos_a, pontos_b e/ou status", 400)
    for campo in ("pontos_a", "pontos_b"):
        if campo in dados and (not isinstance(dados[campo], int) or isinstance(dados[campo], bool) or dados[campo] < 0):
            return erro(f"{campo} deve ser inteiro não negativo", 400)
    if "status" in dados and dados["status"] not in STATUS:
        return erro("Status inválido", 400)
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
