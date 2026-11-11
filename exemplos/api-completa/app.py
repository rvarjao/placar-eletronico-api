import hashlib
import hmac
import os
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from urllib.parse import urlparse

from flask import Flask, g, jsonify, render_template, request
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from admin_panel import admin_bp, autenticar_token, registrar_requisicao
from db_supabase import db, SupabaseError

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "troque-esta-chave-em-producao")
app.register_blueprint(admin_bp)
API_KEY = os.getenv("API_KEY", "")  # Compatibilidade opcional, desabilitada por padrão
DEPLOY_TOKEN = os.getenv("DEPLOY_TOKEN", "")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = Path(__file__).with_name("requirements.txt")
REQUIREMENTS_STAMP = Path(__file__).with_name(".requirements.sha256")
CAMPOS = ("nome_equipe_a", "nome_equipe_b", "modalidade")
STATUS = {"aguardando", "em_andamento", "encerrado"}

def ler():
    return db().all("placares", order="id.asc")

def localizar(id):
    return db().one("placares", filters={"id": f"eq.{id}"})

def erro(mensagem, status):
    return jsonify({"erro": mensagem}), status

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
    g.placar_id = None

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
    if API_KEY and chave_legada and hmac.compare_digest(chave_legada, API_KEY):
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
                getattr(g, "placar_id", None),
            )
        except SupabaseError:
            app.logger.exception("Não foi possível registrar a requisição da API")
    return resposta

def situacao_projeto(url):
    """Classifica o link do grupo para o card da página inicial."""
    if not url:
        return {"rotulo": "Aguardando publicação", "acao": None, "publicado": False}
    host = (urlparse(url).hostname or "").lower()
    if host in ("github.com", "www.github.com"):
        return {"rotulo": "Em desenvolvimento", "acao": "Ver repositório", "publicado": True}
    return {"rotulo": "Disponível", "acao": "Acessar projeto", "publicado": True}


def equipes_publicas():
    grupos = db().all("grupos", columns="id,nome,descricao,url,integrantes(id)",
                      filters={"ativo": "eq.1"}, order="id.asc")
    equipes = []
    for posicao, grupo in enumerate(grupos, start=1):
        individual = len(grupo.get("integrantes") or []) == 1
        equipes.append({
            "nome": grupo["nome"],
            "descricao": grupo.get("descricao"),
            "url": grupo.get("url"),
            "categoria": "Projeto individual" if individual else f"Equipe {posicao:02d}",
            **situacao_projeto(grupo.get("url")),
        })
    return equipes


@app.get("/")
def inicio():
    try:
        equipes = equipes_publicas()
    except SupabaseError:
        app.logger.exception("Não foi possível carregar as equipes da página inicial")
        equipes = None
    return render_template("index.html", equipes=equipes)


def instalar_dependencias():
    """Instala o requirements.txt no virtualenv do app quando ele mudou desde a última instalação."""
    if not REQUIREMENTS.exists():
        return {"erro": False, "saida": "requirements.txt não encontrado"}

    atual = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    instalado = REQUIREMENTS_STAMP.read_text().strip() if REQUIREMENTS_STAMP.exists() else ""
    if atual == instalado:
        return {"erro": False, "saida": "dependências já atualizadas"}

    # sys.prefix aponta para o virtualenv; sys.executable pode ser o binário do uWSGI
    python = Path(sys.prefix) / "bin" / "python"
    try:
        pip = subprocess.run(
            [str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(REQUIREMENTS)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"erro": True, "saida": f"{e.__class__.__name__}: {e}"}

    if pip.returncode != 0:
        return {"erro": True, "saida": (pip.stderr.strip() or pip.stdout.strip())[-2000:]}

    REQUIREMENTS_STAMP.write_text(atual)
    return {"erro": False, "saida": "dependências instaladas"}


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

    dependencias = instalar_dependencias()
    if dependencias["erro"]:
        return jsonify({"erro": "Falha ao instalar dependências", "saida": saida, "dependencias": dependencias["saida"]}), 500

    return jsonify({"status": "updated", "saida": saida, "dependencias": dependencias["saida"]}), 200


@app.get("/api/placares")
def listar():
    return jsonify(ler()), 200

@app.get("/api/placares/<int:id>")
def consultar(id):
    placar = localizar(id)
    if placar:
        g.placar_id = id
    return (jsonify(placar), 200) if placar else erro("Placar não encontrado", 404)

@app.post("/api/placares/criar")
def criar():
    dados = request.get_json(silent=True)
    mensagem = validar_equipes(dados)
    if mensagem:
        return erro(mensagem, 400)
    placar = db().insert("placares", {**{c: dados[c].strip() for c in CAMPOS},
                                      "status": "aguardando", "pontos_a": 0,
                                      "pontos_b": 0, "tempo_partida": 0})
    g.placar_id = placar["id"]
    return jsonify(placar), 201, {"Location": f"/api/placares/{placar['id']}"}

@app.put("/api/placares/<int:id>")
def substituir(id):
    dados = request.get_json(silent=True)
    mensagem = validar_equipes(dados)
    if mensagem:
        return erro(mensagem, 400)
    if not pontos_validos(dados) or not tempo_valido(dados) or dados.get("status") not in STATUS:
        return erro("Informe status válido, pontos_a/pontos_b e tempo_partida como inteiros não negativos", 400)
    novo = {**{c: dados[c].strip() for c in CAMPOS},
            "status": dados["status"], "pontos_a": dados["pontos_a"],
            "pontos_b": dados["pontos_b"], "tempo_partida": dados["tempo_partida"]}
    atualizado = db().update("placares", novo, {"id": f"eq.{id}"})
    if not atualizado:
        return erro("Placar não encontrado", 404)
    g.placar_id = id
    return jsonify(atualizado[0]), 200

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
    atualizado = db().update("placares", dados, {"id": f"eq.{id}"})
    if not atualizado:
        return erro("Placar não encontrado", 404)
    g.placar_id = id
    return jsonify(atualizado[0]), 200

@app.delete("/api/placares/<int:id>")
def excluir(id):
    # A FK do histórico usa ON DELETE SET NULL para preservar o log.
    excluidos = db().delete("placares", {"id": f"eq.{id}"})
    if not excluidos:
        return erro("Placar não encontrado", 404)
    # O placar foi removido: histórico novo também fica sem FK.
    return "", 204

@app.errorhandler(SupabaseError)
def erro_supabase(error):
    app.logger.exception("Falha de persistência no Supabase")
    return erro("Banco de dados temporariamente indisponível", 503)

def carregar_exemplo(nome, caminho):
    """Carrega uma aplicação Flask de exemplo sem exigir nomes de pacotes válidos."""
    import importlib.util
    import sys

    especificacao = importlib.util.spec_from_file_location(nome, caminho)
    modulo = importlib.util.module_from_spec(especificacao)
    sys.modules[nome] = modulo
    especificacao.loader.exec_module(modulo)
    return modulo


def montar_exemplos():
    placar = carregar_exemplo(
        "placar_eletronico_exemplo",
        PROJECT_ROOT / "exemplos" / "placar-eletronico" / "app.py",
    )
    campeonato = carregar_exemplo(
        "campeonato_exemplo",
        PROJECT_ROOT / "exemplos" / "campeonato" / "app.py",
    )

    # Os dois sistemas continuam independentes: cada um guarda o próprio token, informado
    # pelo administrador na tela /configuracao de cada um. Aqui só os ligamos a este servidor.
    for exemplo in (placar, campeonato):
        exemplo.API_INTERNA = app                    # API neste servidor: chamada em processo, sem HTTP
        exemplo.ADMIN_LOGIN_URL = "/admin/login"     # a tela de configuração exige o admin deste painel
        exemplo.app.secret_key = app.config["SECRET_KEY"]  # mesma chave: a sessão do admin vale nos três

    # Sem endereço salvo na tela, a API é este servidor. As variáveis abaixo são opcionais.
    campeonato.PLACAR_URL = os.getenv("EXEMPLO_PLACAR_URL", "").strip().rstrip("/")
    campeonato.PLACAR_TOKEN = os.getenv("EXEMPLO_PLACAR_TOKEN", "").strip()
    campeonato.PLACAR_TELAS_URL = os.getenv("EXEMPLO_PLACAR_TELAS_URL", "/exemplos/placar-eletronico")
    placar.PLACAR_URL = ""
    placar.PLACAR_TOKEN = ""

    if os.getenv("EXEMPLO_POLLING", "1") == "1":
        campeonato.Thread(target=campeonato.polling, daemon=True).start()

    return DispatcherMiddleware(
        app.wsgi_app,
        {
            "/exemplos/campeonato": campeonato.app,
            "/exemplos/placar-eletronico": placar.app,
        },
    )


app.wsgi_app = montar_exemplos()


if __name__ == "__main__":
    app.run(debug=True)
