import hashlib
import hmac
import os
import re
import secrets
from collections import Counter
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from db_supabase import db, SupabaseError


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def agora_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def autenticar_token(token):
    if not token:
        return None
    registro = db().one("tokens_api", columns="grupo_id",
                        filters={"token_hash": f"eq.{hash_token(token)}", "ativo": "eq.1"})
    if registro is None:
        return None
    return db().one("grupos", columns="id,nome,turma",
                    filters={"id": f"eq.{registro['grupo_id']}", "ativo": "eq.1"})


def registrar_requisicao(grupo_id, metodo, rota, status, duracao_ms, placar_id=None):
    db().insert("requisicoes_api", {
        "grupo_id": grupo_id, "placar_id": placar_id,
        "metodo": metodo, "rota": rota, "status": status,
        "duracao_ms": duracao_ms, "criado_em": agora_iso(),
    })


def admin_autenticado(funcao):
    @wraps(funcao)
    def decorada(*args, **kwargs):
        if not session.get("admin_autenticado"):
            return redirect(url_for("admin.login"))
        return funcao(*args, **kwargs)
    return decorada


def token_csrf():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def csrf_valido():
    recebido = request.form.get("csrf_token", "")
    esperado = session.get("csrf_token", "")
    return bool(esperado) and hmac.compare_digest(recebido, esperado)


@admin_bp.context_processor
def contexto_admin():
    return {"csrf_token": token_csrf}


def destino_seguro(destino):
    if destino.startswith("/") and not destino.startswith("//") and "\\" not in destino:
        return destino
    return ""


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    proximo = destino_seguro(request.values.get("next", ""))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        try:
            usuario = db().autenticar_usuario(email, senha) if email and senha else None
        except SupabaseError:
            flash("Não foi possível contatar o Supabase. Tente novamente.", "erro")
            return render_template("admin/login.html", proximo=proximo, email=email)
        if usuario and email_autorizado(usuario.get("email", "")):
            session.clear()
            session["admin_autenticado"] = True
            session["admin_usuario_id"] = usuario.get("id")
            session["admin_email"] = usuario.get("email")
            token_csrf()
            return redirect(proximo or url_for("admin.dashboard"))
        flash("E-mail ou senha inválidos.", "erro")
    return render_template("admin/login.html", proximo=proximo, email="")


def email_autorizado(email):
    """Se ADMIN_EMAILS estiver definido, restringe o painel a esses e-mails."""
    permitidos = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
    return bool(email) and (not permitidos or email.lower() in permitidos)


@admin_bp.post("/logout")
@admin_autenticado
def logout():
    if not csrf_valido():
        return "Requisição inválida", 400
    session.clear()
    return redirect(url_for("admin.login"))


def listar_grupos():
    grupos = db().all("grupos", order="nome.asc")
    tokens = db().all("tokens_api", columns="grupo_id,prefixo,ativo",
                      filters={"ativo": "eq.1"}, order="id.desc")
    por_grupo = {}
    for token in tokens:
        por_grupo.setdefault(token["grupo_id"], token)
    return [{**grupo,
             "prefixo": por_grupo.get(grupo["id"], {}).get("prefixo"),
             "token_ativo": por_grupo.get(grupo["id"], {}).get("ativo")}
            for grupo in grupos]


@admin_bp.get("/")
@admin_autenticado
def dashboard():
    grupos_raw = db().all("grupos", order="nome.asc")
    requisicoes = db().all("requisicoes_api", order="id.desc")
    agora = datetime.now(timezone.utc).date()
    hoje = [r for r in requisicoes if datetime.fromisoformat(
        r["criado_em"].replace("Z", "+00:00")).astimezone(timezone.utc).date() == agora]
    contagem = Counter(r["grupo_id"] for r in requisicoes)
    erros = Counter(r["grupo_id"] for r in requisicoes if r["status"] >= 400)
    metodos = Counter(r["metodo"] for r in requisicoes)
    por_grupo = {}
    for r in requisicoes:
        if r["grupo_id"] is None:
            continue
        info = por_grupo.setdefault(r["grupo_id"], {"primeira": r["criado_em"], "ultima": r["criado_em"]})
        info["primeira"] = min(info["primeira"], r["criado_em"])
        info["ultima"] = max(info["ultima"], r["criado_em"])
    resumo = {
        "grupos_ativos": sum(g["ativo"] == 1 for g in grupos_raw),
        "requisicoes_hoje": len(hoje),
        "erros_hoje": sum(r["status"] >= 400 for r in hoje),
        "nunca_conectaram": sum(g["ativo"] == 1 and not contagem[g["id"]] for g in grupos_raw),
    }
    grupos = [{**g,
               "total_requisicoes": contagem[g["id"]],
               "total_erros": erros[g["id"]],
               "primeira_requisicao": por_grupo.get(g["id"], {}).get("primeira"),
               "ultima_requisicao": por_grupo.get(g["id"], {}).get("ultima")}
              for g in grupos_raw]
    grupos.sort(key=lambda g: (g["ultima_requisicao"] is not None, g["ultima_requisicao"] or ""), reverse=True)
    nomes = {g["id"]: g["nome"] for g in grupos_raw}
    recentes = [{**r, "grupo": nomes.get(r["grupo_id"], "Não identificado")}
               for r in requisicoes[:100]]
    return render_template("admin/dashboard.html", resumo=resumo, grupos=grupos,
                           metodos=[{"metodo": m, "total": n} for m, n in metodos.most_common()],
                           recentes=recentes)


@admin_bp.get("/grupos")
@admin_autenticado
def grupos():
    return render_template("admin/grupos.html", grupos=listar_grupos(), novo_token=None)


def dados_do_formulario():
    """Lê e valida os campos do grupo. Retorna (dados, erro)."""
    nome = request.form.get("nome", "").strip()
    turma = request.form.get("turma", "").strip()
    descricao = request.form.get("descricao", "").strip()
    url = request.form.get("url", "").strip()
    integrantes = [linha.strip() for linha in request.form.get("integrantes", "").splitlines()
                   if linha.strip()]
    if not nome:
        return None, "Informe o nome do grupo."
    if url:
        # Sem esquema (ex.: "site.github.io") assume https; "javascript:" etc. é recusado.
        if not re.match(r"^[a-z][a-z0-9+.-]*:(?!\d)", url, re.IGNORECASE):
            url = "https://" + url
        partes = urlparse(url)
        if partes.scheme not in ("http", "https") or not partes.netloc:
            return None, "Informe uma URL válida (http:// ou https://)."
    return {"nome": nome, "turma": turma or None, "descricao": descricao or None,
            "url": url or None, "integrantes": integrantes}, None


@admin_bp.post("/grupos")
@admin_autenticado
def criar_grupo():
    if not csrf_valido():
        return "Requisição inválida", 400
    dados, erro = dados_do_formulario()
    if erro:
        flash(erro, "erro")
        return redirect(url_for("admin.grupos"))
    token = secrets.token_urlsafe(32)
    grupo = db().insert("grupos", {**dados, "criado_em": agora_iso()})
    db().insert("tokens_api", {"grupo_id": grupo["id"], "token_hash": hash_token(token),
                              "prefixo": token[:8], "criado_em": agora_iso()})
    return render_template("admin/grupos.html", grupos=listar_grupos(),
                           novo_token={"grupo": dados["nome"], "token": token})


@admin_bp.route("/grupos/<int:grupo_id>/editar", methods=["GET", "POST"])
@admin_autenticado
def editar_grupo(grupo_id):
    grupo = db().one("grupos", filters={"id": f"eq.{grupo_id}"})
    if grupo is None:
        return "Grupo não encontrado", 404
    if request.method == "POST":
        if not csrf_valido():
            return "Requisição inválida", 400
        dados, erro = dados_do_formulario()
        if not erro:
            db().update("grupos", dados, {"id": f"eq.{grupo_id}"})
            flash("Grupo atualizado.", "ok")
            return redirect(url_for("admin.grupos"))
        flash(erro, "erro")
        grupo = {**grupo, **request.form, "integrantes": request.form.get("integrantes", "").splitlines()}
    return render_template("admin/grupo_editar.html", grupo=grupo)


@admin_bp.post("/grupos/<int:grupo_id>/novo-token")
@admin_autenticado
def novo_token(grupo_id):
    if not csrf_valido():
        return "Requisição inválida", 400
    grupo = db().one("grupos", columns="id,nome", filters={"id": f"eq.{grupo_id}"})
    if grupo is None:
        return "Grupo não encontrado", 404
    token = secrets.token_urlsafe(32)
    db().update("tokens_api", {"ativo": 0, "revogado_em": agora_iso()},
                {"grupo_id": f"eq.{grupo_id}", "ativo": "eq.1"})
    db().insert("tokens_api", {"grupo_id": grupo_id, "token_hash": hash_token(token),
                              "prefixo": token[:8], "criado_em": agora_iso()})
    return render_template("admin/grupos.html", grupos=listar_grupos(),
                           novo_token={"grupo": grupo["nome"], "token": token})


@admin_bp.post("/grupos/<int:grupo_id>/alternar")
@admin_autenticado
def alternar_grupo(grupo_id):
    if not csrf_valido():
        return "Requisição inválida", 400
    grupo = db().one("grupos", columns="id,ativo", filters={"id": f"eq.{grupo_id}"})
    if grupo is None:
        return "Grupo não encontrado", 404
    db().update("grupos", {"ativo": 0 if grupo["ativo"] else 1}, {"id": f"eq.{grupo_id}"})
    return redirect(url_for("admin.grupos"))
