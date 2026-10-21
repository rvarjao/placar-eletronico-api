import json
import os
import time
from pathlib import Path
from threading import Lock
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
ARQUIVO = Path(__file__).with_name("placares.json")
LOCK = Lock()
API_KEY = os.getenv("API_KEY", "chave-aula-123")  # Somente para aula local
MODALIDADES = {"futebol", "futsal", "basquete", "volei", "handebol", "outro"}
STATUS = {"nao_iniciado", "em_andamento", "pausado", "finalizado"}
INTEIROS = ("tempo", "pontos_equipe_a", "pontos_equipe_b", "faltas_equipe_a", "faltas_equipe_b")
ALTERAVEIS = {"status", "etapa", "detalhes", *INTEIROS}

# Valores iniciais por modalidade: basquete usa cronômetro regressivo (quarto de 10 min)
PADROES = {
    "futebol": {"etapa": "1º tempo", "tempo": 0, "detalhes": {}},
    "futsal": {"etapa": "1º tempo", "tempo": 0, "detalhes": {}},
    "basquete": {"etapa": "1º quarto", "tempo": 600, "detalhes": {}},
    "volei": {"etapa": "1º set", "tempo": 0, "detalhes": {"sets_equipe_a": 0, "sets_equipe_b": 0}},
    "handebol": {"etapa": "1º tempo", "tempo": 0, "detalhes": {}},
    "outro": {"etapa": "", "tempo": 0, "detalhes": {}},
}

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

def inteiro_valido(valor):
    return isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0

# O cronômetro roda no servidor: enquanto em_andamento, guardamos o instante de início
# em "_inicio" e calculamos o tempo atual a cada consulta. Campos com "_" são internos.
def tempo_atual(placar):
    if placar["status"] != "em_andamento" or not placar.get("_inicio"):
        return placar["tempo"]
    decorrido = int(time.time() - placar["_inicio"])
    if placar["modalidade"] == "basquete":
        return max(0, placar["tempo"] - decorrido)
    return placar["tempo"] + decorrido

def publico(placar):
    dados = {k: v for k, v in placar.items() if not k.startswith("_")}
    dados["tempo"] = tempo_atual(placar)
    return dados

def validar_criacao(dados):
    if not isinstance(dados, dict):
        return "Envie um objeto JSON"
    if not all(isinstance(dados.get(c), str) and dados[c].strip() for c in ("nome_equipe_a", "nome_equipe_b")):
        return "Informe nome_equipe_a e nome_equipe_b como textos não vazios"
    if dados.get("modalidade") not in MODALIDADES:
        return f"modalidade deve ser uma de: {', '.join(sorted(MODALIDADES))}"
    if "etapa" in dados and not isinstance(dados["etapa"], str):
        return "etapa deve ser texto"
    if "tempo" in dados and not inteiro_valido(dados["tempo"]):
        return "tempo deve ser inteiro não negativo"
    return None

def validar_alteracao(dados):
    if not isinstance(dados, dict) or not dados:
        return "Envie um objeto JSON com os campos alterados"
    proibidos = set(dados) - ALTERAVEIS
    if proibidos:
        return f"Campos não alteráveis: {', '.join(sorted(proibidos))}"
    for campo in INTEIROS:
        if campo in dados and not inteiro_valido(dados[campo]):
            return f"{campo} deve ser inteiro não negativo"
    if "status" in dados and dados["status"] not in STATUS:
        return f"status deve ser um de: {', '.join(sorted(STATUS))}"
    if "etapa" in dados and not isinstance(dados["etapa"], str):
        return "etapa deve ser texto"
    if "detalhes" in dados and not isinstance(dados["detalhes"], dict):
        return "detalhes deve ser um objeto JSON"
    return None

@app.before_request
def proteger_escrita():
    if request.path.startswith("/api/") and request.method in {"POST", "PATCH"} and request.headers.get("X-API-Key") != API_KEY:
        return erro("API Key ausente ou inválida", 401)

# ---------- API REST ----------

@app.get("/api/placares")
def listar():
    with LOCK:
        return jsonify([publico(p) for p in ler()]), 200

@app.get("/api/placares/<int:id>")
def consultar(id):
    with LOCK:
        placar = localizar(ler(), id)
    return (jsonify(publico(placar)), 200) if placar else erro("placar_nao_encontrado", 404)

@app.post("/api/placares")
def criar():
    dados = request.get_json(silent=True)
    mensagem = validar_criacao(dados)
    if mensagem:
        return erro(mensagem, 400)
    padrao = PADROES[dados["modalidade"]]
    with LOCK:
        placares = ler()
        id = max((p["id"] for p in placares), default=0) + 1
        placar = {
            "id": id,
            "nome_equipe_a": dados["nome_equipe_a"].strip(),
            "nome_equipe_b": dados["nome_equipe_b"].strip(),
            "modalidade": dados["modalidade"],
            "status": "nao_iniciado",
            "tempo": dados.get("tempo", padrao["tempo"]),
            "etapa": dados.get("etapa", padrao["etapa"]),
            "pontos_equipe_a": 0,
            "pontos_equipe_b": 0,
            "faltas_equipe_a": 0,
            "faltas_equipe_b": 0,
            "detalhes": dict(padrao["detalhes"]),
            "_inicio": None,
        }
        placares.append(placar)
        salvar(placares)
    return jsonify(publico(placar)), 201, {"Location": f"/api/placares/{id}"}

@app.patch("/api/placares/<int:id>")
def alterar(id):
    dados = request.get_json(silent=True)
    mensagem = validar_alteracao(dados)
    if mensagem:
        return erro(mensagem, 400)
    with LOCK:
        placares = ler()
        placar = localizar(placares, id)
        if placar is None:
            return erro("placar_nao_encontrado", 404)
        if placar["status"] == "finalizado":
            return erro("Partida finalizada não pode ser alterada", 409)
        # Congela o cronômetro, aplica as mudanças e, se ainda em andamento, reinicia a contagem
        placar["tempo"] = tempo_atual(placar)
        placar.update(dados)
        placar["_inicio"] = time.time() if placar["status"] == "em_andamento" else None
        salvar(placares)
    return jsonify(publico(placar)), 200

# ---------- Telas ----------

@app.get("/")
def inicio():
    return render_template("lista.html")

@app.get("/operador/<int:id>")
def operador(id):
    return render_template("operador.html", id=id)

@app.get("/placar/<int:id>")
def telao(id):
    return render_template("telao.html", id=id)

if __name__ == "__main__":
    # host 0.0.0.0 permite acesso pelos outros computadores da rede local
    app.run(host="0.0.0.0", port=int(os.getenv("PORTA", "5001")), debug=True)
