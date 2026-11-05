import hmac
import json
import os
import secrets
import time
from functools import wraps
from itertools import combinations
from pathlib import Path
from threading import Lock, Thread
from urllib.parse import urlencode

import requests
from flask import Flask, flash, jsonify, redirect, render_template, request, session

app = Flask(__name__)
# Necessário para a sessão da tela de configuração. No servidor principal este valor é
# substituído pela SECRET_KEY dele, o que permite reaproveitar o login do administrador.
app.secret_key = os.getenv("SECRET_KEY", "troque-esta-chave-em-producao")
ARQUIVO = Path(__file__).with_name("campeonato.json")
CONEXAO_ARQUIVO = Path(__file__).with_name("conexao_api.json")  # token salvo pela tela; fica fora do git
LOCK = Lock()

# Valores iniciais da conexão (variáveis de ambiente). O que for salvo na tela de
# configuração tem prioridade sobre eles.
PLACAR_URL = os.getenv("PLACAR_URL", "").strip().rstrip("/")
PLACAR_TOKEN = os.getenv("PLACAR_TOKEN", "").strip()
PLACAR_TELAS_URL = os.getenv("PLACAR_TELAS_URL", "").strip().rstrip("/")
URL_LOCAL_PADRAO = "http://127.0.0.1:5001"
PLACAR_API_KEY = os.getenv("PLACAR_API_KEY", "chave-aula-123").strip()
PLACAR_CREATE_PATH = os.getenv("PLACAR_CREATE_PATH", "").strip()

# Definidos pelo servidor principal quando este sistema roda dentro dele:
API_INTERNA = None      # aplicação Flask da API: chamadas feitas em processo, sem passar pela rede
ADMIN_LOGIN_URL = os.getenv("ADMIN_LOGIN_URL", "")  # vazio = tela de configuração aberta (uso local)

INTERVALO_POLLING = int(os.getenv("INTERVALO_POLLING", "5"))
TIMEOUT = 3
MODALIDADES = {"futebol", "futsal", "basquete", "volei", "handebol", "outro"}

# Estados de uma partida no campeonato:
# agendada -> em_acompanhamento (placar criado, polling ativo) -> encerrada (resultado registrado)
#                               \-> erro_placar (placar sumiu: 404; não recria automaticamente)

def ler():
    if ARQUIVO.exists():
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    return {"nome": "", "modalidade": "futsal", "equipes": [], "partidas": []}

def salvar(campeonato):
    temporario = ARQUIVO.with_suffix(".tmp")
    temporario.write_text(json.dumps(campeonato, ensure_ascii=False, indent=2), encoding="utf-8")
    temporario.replace(ARQUIVO)

def erro(mensagem, status):
    return jsonify({"erro": mensagem}), status

def localizar(partidas, id):
    return next((p for p in partidas if p["id"] == id), None)

def gerar_partidas(equipes):
    # Turno único, todos contra todos
    return [
        {"id": i, "equipe_a": a, "equipe_b": b, "status": "agendada", "placar_id": None,
         "placar": None, "resultado": None, "ultimo_erro": None}
        for i, (a, b) in enumerate(combinations(equipes, 2), start=1)
    ]

def classificacao(campeonato):
    # Vitória 3, empate 1, derrota 0. Desempate: vitórias, saldo, pontos marcados
    tabela = {e: {"equipe": e, "pontos": 0, "jogos": 0, "vitorias": 0, "empates": 0, "derrotas": 0, "marcados": 0, "sofridos": 0}
              for e in campeonato["equipes"]}
    for partida in campeonato["partidas"]:
        r = partida["resultado"]
        if not r:
            continue
        for equipe, pro, contra in ((partida["equipe_a"], r["pontos_a"], r["pontos_b"]), (partida["equipe_b"], r["pontos_b"], r["pontos_a"])):
            linha = tabela[equipe]
            linha["jogos"] += 1
            linha["marcados"] += pro
            linha["sofridos"] += contra
            if pro > contra:
                linha["vitorias"] += 1
                linha["pontos"] += 3
            elif pro == contra:
                linha["empates"] += 1
                linha["pontos"] += 1
            else:
                linha["derrotas"] += 1
    for linha in tabela.values():
        linha["saldo"] = linha["marcados"] - linha["sofridos"]
    return sorted(tabela.values(), key=lambda l: (l["pontos"], l["vitorias"], l["saldo"], l["marcados"]), reverse=True)

def resultado_final(placar, modalidade):
    # No vôlei o vencedor é quem tem mais sets; nos demais, os pontos/gols
    if modalidade == "volei":
        d = placar.get("detalhes", {})
        return {"pontos_a": d.get("sets_equipe_a", 0), "pontos_b": d.get("sets_equipe_b", 0)}
    return {"pontos_a": placar["pontos_equipe_a"], "pontos_b": placar["pontos_equipe_b"]}

# ---------- Integração com o Placar Eletrônico ----------

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
    conexao = {"url": PLACAR_URL, "token": PLACAR_TOKEN, "telas_url": PLACAR_TELAS_URL}
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


def caminho_criacao(conexao):
    if PLACAR_CREATE_PATH:
        return PLACAR_CREATE_PATH
    return "/api/placares/criar" if conexao["token"] else "/api/placares"


def token_obrigatorio(conexao):
    """Dentro do servidor principal a API exige o token do grupo; sem ele nenhuma chamada passa."""
    return destino_api(conexao) is None and not conexao["token"]


def chamar_api(metodo, caminho, corpo=None, conexao=None):
    """Chama a API de placares. Retorna (status, json_ou_None, texto).

    Bearer identifica o grupo na API publicada; X-API-Key mantém o placar local compatível.
    No mesmo servidor a chamada é feita em processo: uma requisição HTTP para si mesmo
    ficaria presa esperando o único processo atender."""
    conexao = conexao or ler_conexao()
    if conexao["token"]:
        cabecalhos = {"Authorization": f"Bearer {conexao['token']}"}
    else:
        cabecalhos = {"X-API-Key": PLACAR_API_KEY}
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


def normalizar_placar(placar):
    """Converte os formatos da API publicada e do exemplo local para um formato único."""
    return {
        "status": placar.get("status", ""),
        "tempo": placar.get("tempo_partida", placar.get("tempo", 0)),
        "etapa": placar.get("etapa", ""),
        "pontos_equipe_a": placar.get("pontos_a", placar.get("pontos_equipe_a", 0)),
        "pontos_equipe_b": placar.get("pontos_b", placar.get("pontos_equipe_b", 0)),
        "faltas_equipe_a": placar.get("faltas_equipe_a", 0),
        "faltas_equipe_b": placar.get("faltas_equipe_b", 0),
        "detalhes": placar.get("detalhes", {}),
    }


def consultar_placar(placar_id):
    """Retorna (placar, mensagem_erro, deve_parar)."""
    conexao = ler_conexao()
    if token_obrigatorio(conexao):
        return None, "Token da API não configurado; peça ao administrador para informá-lo na tela de configuração", False
    try:
        status, dados, _ = chamar_api("GET", f"/api/placares/{placar_id}", conexao=conexao)
    except ApiIndisponivel as e:
        return None, f"Placar indisponível ({e}); tentando novamente", False
    if status == 404:
        return None, f"Placar {placar_id} não existe mais no servidor", True
    if status == 401:
        return None, "A API recusou o token (401); confira a configuração", False
    if status >= 500:
        return None, f"Placar respondeu {status}; tentando novamente", False
    if status != 200 or not isinstance(dados, dict):
        return None, f"Resposta inesperada {status}", False
    return normalizar_placar(dados), None, False

def sincronizar_partida(partida, modalidade):
    placar, mensagem, parar = consultar_placar(partida["placar_id"])
    partida["ultimo_erro"] = mensagem
    if parar:
        partida["status"] = "erro_placar"
    if placar is None:
        return
    partida["placar"] = {c: placar.get(c) for c in ("status", "tempo", "etapa", "pontos_equipe_a", "pontos_equipe_b",
                                                    "faltas_equipe_a", "faltas_equipe_b", "detalhes")}
    if placar["status"] in {"finalizado", "encerrado"}:
        partida["status"] = "encerrada"
        partida["resultado"] = resultado_final(placar, modalidade)

def polling():
    # Thread de fundo: a cada INTERVALO_POLLING segundos consulta apenas as partidas em acompanhamento.
    # As requisições HTTP são feitas fora do LOCK para não travar a aplicação se o placar demorar.
    while True:
        time.sleep(INTERVALO_POLLING)
        with LOCK:
            campeonato = ler()
        acompanhadas = [p for p in campeonato["partidas"] if p["status"] == "em_acompanhamento"]
        if not acompanhadas:
            continue
        for partida in acompanhadas:
            sincronizar_partida(partida, campeonato["modalidade"])
        with LOCK:
            atual = ler()
            for partida in acompanhadas:
                destino = localizar(atual["partidas"], partida["id"])
                # Só grava se o campeonato não foi recriado nesse meio-tempo
                if destino and destino["placar_id"] == partida["placar_id"]:
                    destino.update(partida)
            salvar(atual)

# ---------- API do Campeonato ----------

@app.get("/api/campeonato")
def consultar():
    with LOCK:
        campeonato = ler()
    conexao = ler_conexao()
    return jsonify({
        **campeonato,
        "classificacao": classificacao(campeonato),
        "placar_url": destino_api(conexao) or "",
        "telas_url": conexao["telas_url"],
        "api_remota": bool(conexao["token"]),
        "conexao": {"configurada": not token_obrigatorio(conexao), "destino": descrever_destino(conexao)},
    }), 200

@app.post("/api/campeonato")
def criar_campeonato():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict) or not isinstance(dados.get("nome"), str) or not dados["nome"].strip():
        return erro("Informe o nome do campeonato", 400)
    if dados.get("modalidade") not in MODALIDADES:
        return erro(f"modalidade deve ser uma de: {', '.join(sorted(MODALIDADES))}", 400)
    equipes = dados.get("equipes")
    if not isinstance(equipes, list) or not all(isinstance(e, str) and e.strip() for e in equipes):
        return erro("equipes deve ser uma lista de nomes", 400)
    equipes = list(dict.fromkeys(e.strip() for e in equipes))  # remove repetidas mantendo a ordem
    if len(equipes) < 2:
        return erro("Informe pelo menos duas equipes diferentes", 400)
    campeonato = {"nome": dados["nome"].strip(), "modalidade": dados["modalidade"], "equipes": equipes,
                  "partidas": gerar_partidas(equipes)}
    with LOCK:
        salvar(campeonato)
    return jsonify(campeonato), 201

@app.post("/api/partidas/<int:id>/iniciar")
def iniciar_partida(id):
    with LOCK:
        campeonato = ler()
        partida = localizar(campeonato["partidas"], id)
    if partida is None:
        return erro("Partida não encontrada", 404)
    if partida["placar_id"] is not None:
        return erro("Esta partida já possui placar", 409)
    corpo = {"nome_equipe_a": partida["equipe_a"], "nome_equipe_b": partida["equipe_b"], "modalidade": campeonato["modalidade"]}
    conexao = ler_conexao()
    if token_obrigatorio(conexao):
        return erro("Token da API não configurado. O administrador precisa informá-lo na tela de configuração.", 409)
    try:
        status, placar, texto = chamar_api("POST", caminho_criacao(conexao), corpo, conexao)
    except ApiIndisponivel as e:
        return erro(f"Placar Eletrônico indisponível: {e}", 503)
    if status == 401:
        return erro("A API recusou o token (401). Confira o token na tela de configuração.", 502)
    if status != 201 or not isinstance(placar, dict) or "id" not in placar:
        return erro(f"Placar recusou a criação ({status}): {texto[:200]}", 502)
    with LOCK:
        campeonato = ler()
        partida = localizar(campeonato["partidas"], id)
        partida.update({"placar_id": placar["id"], "status": "em_acompanhamento", "ultimo_erro": None})
        salvar(campeonato)
    return jsonify(partida), 200

@app.post("/api/partidas/<int:id>/sincronizar")
def sincronizar_agora(id):
    # Consulta imediata, útil para demonstrar sem esperar o próximo ciclo do polling
    with LOCK:
        campeonato = ler()
        partida = localizar(campeonato["partidas"], id)
        if partida is None:
            return erro("Partida não encontrada", 404)
        if partida["placar_id"] is None:
            return erro("Partida ainda não possui placar", 409)
        sincronizar_partida(partida, campeonato["modalidade"])
        salvar(campeonato)
    return jsonify(partida), 200

@app.get("/")
def inicio():
    return render_template("index.html")

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

def url_valida(valor, permitir_relativa=False):
    if not valor:
        return True
    if permitir_relativa and valor.startswith("/") and not valor.startswith("//"):
        return True
    return valor.startswith(("http://", "https://"))

def testar_conexao():
    """Faz uma consulta simples à API com o token salvo. Retorna (ok, mensagem)."""
    conexao = ler_conexao()
    if token_obrigatorio(conexao):
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
        telas_url=conexao["telas_url"],
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
    telas_url = request.form.get("telas_url", "").strip().rstrip("/")
    token = request.form.get("token", "").strip()
    if not url_valida(url) or not url_valida(telas_url, permitir_relativa=True):
        flash("Os endereços precisam começar com http:// ou https:// (as telas também aceitam um caminho como /exemplos/placar-eletronico).", "erro")
        return redirect(request.script_root + "/configuracao")
    salvo = ler_arquivo_conexao()
    salvo["url"] = url
    salvo["telas_url"] = telas_url
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
    Thread(target=polling, daemon=True).start()
    # use_reloader=False evita que o modo debug inicie a thread de polling duas vezes
    app.run(host="0.0.0.0", port=int(os.getenv("PORTA", "5002")), debug=True, use_reloader=False)
