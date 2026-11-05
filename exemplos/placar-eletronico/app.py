import hmac
import json
import os
import secrets
import time
from functools import wraps
from pathlib import Path
from threading import Lock
from urllib.parse import urlencode

import requests
from flask import Flask, flash, jsonify, redirect, render_template, request, session

app = Flask(__name__)
# Necessário para a sessão da tela de configuração. No servidor principal este valor é
# substituído pela SECRET_KEY dele, o que permite reaproveitar o login do administrador.
app.secret_key = os.getenv("SECRET_KEY", "troque-esta-chave-em-producao")
ESTADO_ARQUIVO = Path(__file__).with_name("estado_local.json")    # etapa, faltas, sets e cronômetro
CONEXAO_ARQUIVO = Path(__file__).with_name("conexao_api.json")    # token salvo pela tela; fica fora do git
LOCK = Lock()
API_KEY = os.getenv("API_KEY", "chave-aula-123")  # Protege as telas de operador. Somente para aula local

# Valores iniciais da conexão (variáveis de ambiente). O que for salvo na tela de
# configuração tem prioridade sobre eles.
PLACAR_URL = os.getenv("PLACAR_URL", "").strip().rstrip("/")
PLACAR_TOKEN = os.getenv("PLACAR_TOKEN", "").strip()
URL_LOCAL_PADRAO = "http://127.0.0.1:5000"  # api-completa rodando na sua máquina
TIMEOUT = 5

# Definidos pelo servidor principal quando este sistema roda dentro dele:
API_INTERNA = None      # aplicação Flask da API: chamadas feitas em processo, sem passar pela rede
ADMIN_LOGIN_URL = os.getenv("ADMIN_LOGIN_URL", "")  # vazio = tela de configuração aberta (uso local)

MODALIDADES = {"futebol", "futsal", "basquete", "volei", "handebol", "outro"}
STATUS = {"nao_iniciado", "em_andamento", "pausado", "finalizado"}
INTEIROS = ("tempo", "pontos_equipe_a", "pontos_equipe_b", "faltas_equipe_a", "faltas_equipe_b")
ALTERAVEIS = {"status", "etapa", "detalhes", *INTEIROS}

# A API guarda apenas nomes, modalidade, status, pontos e tempo decorrido. Os demais
# dados da tela (etapa, faltas, sets, pausa) ficam neste sistema, em estado_local.json.
STATUS_PARA_API = {"nao_iniciado": "aguardando", "em_andamento": "em_andamento",
                   "pausado": "em_andamento", "finalizado": "encerrado"}
STATUS_DA_API = {"aguardando": "nao_iniciado", "em_andamento": "em_andamento", "encerrado": "finalizado"}

# Valores iniciais por modalidade. O basquete mostra cronômetro regressivo (quarto de 10 min);
# na API o tempo é sempre o decorrido, então a tela mostra 600 − decorrido.
PADROES = {
    "futebol": {"etapa": "1º tempo", "detalhes": {}},
    "futsal": {"etapa": "1º tempo", "detalhes": {}},
    "basquete": {"etapa": "1º quarto", "detalhes": {}},
    "volei": {"etapa": "1º set", "detalhes": {"sets_equipe_a": 0, "sets_equipe_b": 0}},
    "handebol": {"etapa": "1º tempo", "detalhes": {}},
    "outro": {"etapa": "", "detalhes": {}},
}
TEMPO_REGRESSIVO = {"basquete": 600}

def erro(mensagem, status):
    return jsonify({"erro": mensagem}), status

def inteiro_valido(valor):
    return isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0

# ---------- Conexão com a API ----------

class ApiIndisponivel(Exception):
    """A API não respondeu (rede, timeout ou servidor fora do ar)."""


def ler_arquivo_conexao():
    try:
        dados = json.loads(CONEXAO_ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def ler_conexao():
    """Conexão efetiva: valores salvos na tela de configuração sobre os padrões do ambiente."""
    conexao = {"url": PLACAR_URL, "token": PLACAR_TOKEN}
    salvo = ler_arquivo_conexao()
    for chave in conexao:
        if isinstance(salvo.get(chave), str):
            conexao[chave] = salvo[chave].strip().rstrip("/")
    return conexao


def salvar_conexao(dados):
    temporario = CONEXAO_ARQUIVO.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(temporario, 0o600)  # o arquivo guarda o token: só o dono lê
    except OSError:
        pass
    temporario.replace(CONEXAO_ARQUIVO)


def destino_api(conexao):
    """URL base da API, ou None quando a API roda neste mesmo servidor (chamada em processo)."""
    if conexao["url"]:
        return conexao["url"]
    return None if API_INTERNA is not None else URL_LOCAL_PADRAO


def descrever_destino(conexao):
    return destino_api(conexao) or "este servidor"


def chamar_api(metodo, caminho, corpo=None, conexao=None):
    """Chama a API de placares com o token do grupo. Retorna (status, json_ou_None, texto).

    No mesmo servidor a chamada é feita em processo: uma requisição HTTP para si mesmo
    ficaria presa esperando o único processo atender."""
    conexao = conexao or ler_conexao()
    cabecalhos = {"Authorization": f"Bearer {conexao['token']}"}
    destino = destino_api(conexao)
    if destino is None:
        from werkzeug.test import Client
        resposta = Client(API_INTERNA, use_cookies=False).open(
            caminho, method=metodo, json=corpo, headers=cabecalhos
        )
        return resposta.status_code, resposta.get_json(silent=True), resposta.get_data(as_text=True)
    try:
        resposta = requests.request(metodo, f"{destino}{caminho}", json=corpo, headers=cabecalhos, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise ApiIndisponivel(e.__class__.__name__) from e
    try:
        dados = resposta.json()
    except ValueError:
        dados = None
    return resposta.status_code, dados, resposta.text


def api(metodo, caminho, corpo=None):
    """Chama a API e devolve (dados, None) ou (None, resposta_de_erro_para_a_tela)."""
    conexao = ler_conexao()
    if not conexao["token"]:
        return None, erro("Token da API não configurado. O administrador precisa informá-lo na tela de configuração.", 503)
    try:
        status, dados, _ = chamar_api(metodo, caminho, corpo, conexao)
    except ApiIndisponivel as e:
        return None, erro(f"API indisponível ({e})", 503)
    if status in (200, 201) and dados is not None:
        return dados, None
    mensagem = dados.get("erro") if isinstance(dados, dict) else None
    if status == 401:
        return None, erro("A API recusou o token. Peça ao administrador para conferir a configuração.", 502)
    if status == 404:
        return None, erro("placar_nao_encontrado", 404)
    if status == 400:
        return None, erro(mensagem or "Requisição inválida", 400)
    return None, erro(mensagem or f"Resposta inesperada da API ({status})", 502)

# ---------- Tradução entre a API e as telas ----------
# O cronômetro roda neste sistema: enquanto em andamento guardamos o instante de início em
# "inicio" e somamos o tempo corrido ao tempo decorrido que a API guarda. A cada alteração o
# valor é congelado e enviado à API como tempo_partida.

def ler_estado():
    try:
        dados = json.loads(ESTADO_ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}

def salvar_estado(estado):
    temporario = ESTADO_ARQUIVO.with_suffix(".tmp")
    temporario.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    temporario.replace(ESTADO_ARQUIVO)

def estado_padrao(modalidade, etapa=None):
    padrao = PADROES.get(modalidade, PADROES["outro"])
    return {"etapa": padrao["etapa"] if etapa is None else etapa, "faltas_equipe_a": 0, "faltas_equipe_b": 0,
            "detalhes": dict(padrao["detalhes"]), "pausado": False, "inicio": None}

def extras_do_placar(placar, estado):
    return {**estado_padrao(placar["modalidade"]), **estado.get(str(placar["id"]), {})}

def decorrido(placar, extras):
    segundos = placar.get("tempo_partida", 0)
    if placar.get("status") == "em_andamento" and extras["inicio"] and not extras["pausado"]:
        segundos += int(time.time() - extras["inicio"])
    return segundos

def status_da_tela(placar, extras):
    status = STATUS_DA_API.get(placar.get("status"), "nao_iniciado")
    return "pausado" if status == "em_andamento" and extras["pausado"] else status

def para_tela(placar, estado):
    """Converte um placar da API (e o estado local) no formato usado pelas telas."""
    extras = extras_do_placar(placar, estado)
    segundos = decorrido(placar, extras)
    regressivo = TEMPO_REGRESSIVO.get(placar["modalidade"])
    return {
        "id": placar["id"],
        "nome_equipe_a": placar["nome_equipe_a"],
        "nome_equipe_b": placar["nome_equipe_b"],
        "modalidade": placar["modalidade"],
        "status": status_da_tela(placar, extras),
        "tempo": max(0, regressivo - segundos) if regressivo else segundos,
        "etapa": extras["etapa"],
        "pontos_equipe_a": placar.get("pontos_a", 0),
        "pontos_equipe_b": placar.get("pontos_b", 0),
        "faltas_equipe_a": extras["faltas_equipe_a"],
        "faltas_equipe_b": extras["faltas_equipe_b"],
        "detalhes": extras["detalhes"],
    }

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

# ---------- API REST (usa a API principal por trás) ----------

@app.get("/api/placares")
def listar():
    lista, falha = api("GET", "/api/placares")
    if falha:
        return falha
    if not isinstance(lista, list):
        return erro("Resposta inesperada da API", 502)
    with LOCK:
        estado = ler_estado()
    return jsonify([para_tela(p, estado) for p in lista]), 200

@app.get("/api/placares/<int:id>")
def consultar(id):
    placar, falha = api("GET", f"/api/placares/{id}")
    if falha:
        return falha
    with LOCK:
        estado = ler_estado()
    return jsonify(para_tela(placar, estado)), 200

@app.post("/api/placares")
def criar():
    dados = request.get_json(silent=True)
    mensagem = validar_criacao(dados)
    if mensagem:
        return erro(mensagem, 400)
    corpo = {campo: dados[campo].strip() for campo in ("nome_equipe_a", "nome_equipe_b", "modalidade")}
    placar, falha = api("POST", "/api/placares/criar", corpo)
    if falha:
        return falha
    extras = estado_padrao(corpo["modalidade"], dados.get("etapa"))
    with LOCK:
        estado = ler_estado()
        estado[str(placar["id"])] = extras
        salvar_estado(estado)
    return jsonify(para_tela(placar, {str(placar["id"]): extras})), 201, {"Location": f"/api/placares/{placar['id']}"}

@app.patch("/api/placares/<int:id>")
def alterar(id):
    dados = request.get_json(silent=True)
    mensagem = validar_alteracao(dados)
    if mensagem:
        return erro(mensagem, 400)
    with LOCK:
        atual, falha = api("GET", f"/api/placares/{id}")
        if falha:
            return falha
        if atual.get("status") == "encerrado":
            return erro("Partida finalizada não pode ser alterada", 409)
        estado = ler_estado()
        extras = extras_do_placar(atual, estado)
        # Congela o cronômetro, aplica as mudanças e, se ainda em andamento, reinicia a contagem
        segundos = decorrido(atual, extras)
        regressivo = TEMPO_REGRESSIVO.get(atual["modalidade"])
        if "tempo" in dados:
            segundos = max(0, regressivo - dados["tempo"]) if regressivo else dados["tempo"]
        status_tela = dados.get("status", status_da_tela(atual, extras))
        for campo in ("etapa", "faltas_equipe_a", "faltas_equipe_b", "detalhes"):
            if campo in dados:
                extras[campo] = dados[campo]
        extras["pausado"] = status_tela == "pausado"
        extras["inicio"] = time.time() if status_tela == "em_andamento" else None
        alteracao = {"status": STATUS_PARA_API[status_tela], "tempo_partida": segundos}
        if "pontos_equipe_a" in dados:
            alteracao["pontos_a"] = dados["pontos_equipe_a"]
        if "pontos_equipe_b" in dados:
            alteracao["pontos_b"] = dados["pontos_equipe_b"]
        novo, falha = api("PATCH", f"/api/placares/{id}", alteracao)
        if falha:
            return falha
        estado[str(id)] = extras
        salvar_estado(estado)
    return jsonify(para_tela(novo, {str(id): extras})), 200

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

# ---------- Tela de configuração da conexão com a API ----------

def exige_admin(funcao):
    """Dentro do servidor principal, só o administrador logado altera a conexão."""
    @wraps(funcao)
    def decorada(*args, **kwargs):
        if ADMIN_LOGIN_URL and not session.get("admin_autenticado"):
            proximo = urlencode({"next": request.script_root + request.path})
            return redirect(f"{ADMIN_LOGIN_URL}?{proximo}")
        return funcao(*args, **kwargs)
    return decorada

def token_csrf():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]

def csrf_valido():
    esperado = session.get("csrf_token", "")
    return bool(esperado) and hmac.compare_digest(request.form.get("csrf_token", ""), esperado)

def url_valida(valor):
    return not valor or valor.startswith(("http://", "https://"))

def testar_conexao():
    """Faz uma consulta simples à API com o token salvo. Retorna (ok, mensagem)."""
    conexao = ler_conexao()
    if not conexao["token"]:
        return False, "Informe o token do grupo para conectar à API."
    try:
        status, _, _ = chamar_api("GET", "/api/placares", conexao=conexao)
    except ApiIndisponivel as e:
        return False, f"A API não respondeu ({e}). Confira o endereço."
    if status == 200:
        return True, f"Conexão OK: a API ({descrever_destino(conexao)}) aceitou o token."
    if status == 401:
        return False, "A API recusou o token (401). Confira o token do grupo no painel administrativo."
    return False, f"Resposta inesperada da API: {status}."

@app.get("/configuracao")
@exige_admin
def tela_configuracao():
    conexao = ler_conexao()
    return render_template(
        "configuracao.html",
        url=conexao["url"],
        tem_token=bool(conexao["token"]),
        prefixo=conexao["token"][:8],
        destino=descrever_destino(conexao),
        csrf_token=token_csrf(),
        grupos_url="/admin/grupos" if ADMIN_LOGIN_URL else "",
    )

@app.post("/configuracao")
@exige_admin
def salvar_configuracao():
    if not csrf_valido():
        return "Requisição inválida", 400
    url = request.form.get("url", "").strip().rstrip("/")
    token = request.form.get("token", "").strip()
    if not url_valida(url):
        flash("O endereço da API precisa começar com http:// ou https://.", "erro")
        return redirect(request.script_root + "/configuracao")
    salvo = ler_arquivo_conexao()
    salvo["url"] = url
    if token:  # campo em branco mantém o token atual
        salvo["token"] = token
    salvar_conexao(salvo)
    ok, mensagem = testar_conexao()
    flash(("Configuração salva. " if ok else "Configuração salva, mas: ") + mensagem, "ok" if ok else "erro")
    return redirect(request.script_root + "/configuracao")

@app.post("/configuracao/testar")
@exige_admin
def testar_configuracao():
    if not csrf_valido():
        return "Requisição inválida", 400
    ok, mensagem = testar_conexao()
    flash(mensagem, "ok" if ok else "erro")
    return redirect(request.script_root + "/configuracao")

@app.post("/configuracao/remover-token")
@exige_admin
def remover_token():
    if not csrf_valido():
        return "Requisição inválida", 400
    salvo = ler_arquivo_conexao()
    salvo["token"] = ""
    salvar_conexao(salvo)
    flash("Token removido.", "ok")
    return redirect(request.script_root + "/configuracao")

if __name__ == "__main__":
    # host 0.0.0.0 permite acesso pelos outros computadores da rede local
    app.run(host="0.0.0.0", port=int(os.getenv("PORTA", "5001")), debug=True)
