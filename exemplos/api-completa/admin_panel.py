import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, session, url_for


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
DATABASE_PATH = Path(__file__).with_name("monitoramento.db")


def agora_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conectar():
    conexao = sqlite3.connect(DATABASE_PATH)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def inicializar_banco():
    with conectar() as conexao:
        conexao.executescript(
            """
            CREATE TABLE IF NOT EXISTS grupos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                turma TEXT,
                ativo INTEGER NOT NULL DEFAULT 1,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tokens_api (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                grupo_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                prefixo TEXT NOT NULL,
                ativo INTEGER NOT NULL DEFAULT 1,
                criado_em TEXT NOT NULL,
                revogado_em TEXT,
                FOREIGN KEY (grupo_id) REFERENCES grupos(id)
            );

            CREATE TABLE IF NOT EXISTS requisicoes_api (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                grupo_id INTEGER,
                metodo TEXT NOT NULL,
                rota TEXT NOT NULL,
                status INTEGER NOT NULL,
                duracao_ms INTEGER NOT NULL,
                criado_em TEXT NOT NULL,
                FOREIGN KEY (grupo_id) REFERENCES grupos(id)
            );

            CREATE INDEX IF NOT EXISTS idx_requisicoes_grupo_data
                ON requisicoes_api (grupo_id, criado_em);
            CREATE INDEX IF NOT EXISTS idx_requisicoes_data
                ON requisicoes_api (criado_em);
            """
        )


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def autenticar_token(token):
    if not token:
        return None

    with conectar() as conexao:
        return conexao.execute(
            """
            SELECT grupos.id, grupos.nome, grupos.turma
            FROM tokens_api
            JOIN grupos ON grupos.id = tokens_api.grupo_id
            WHERE tokens_api.token_hash = ?
              AND tokens_api.ativo = 1
              AND grupos.ativo = 1
            """,
            (hash_token(token),),
        ).fetchone()


def registrar_requisicao(grupo_id, metodo, rota, status, duracao_ms):
    with conectar() as conexao:
        conexao.execute(
            """
            INSERT INTO requisicoes_api
                (grupo_id, metodo, rota, status, duracao_ms, criado_em)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (grupo_id, metodo, rota, status, duracao_ms, agora_iso()),
        )


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


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario_esperado = os.getenv("ADMIN_USERNAME", "admin")
        senha_esperada = os.getenv("ADMIN_PASSWORD", "")
        usuario = request.form.get("usuario", "")
        senha = request.form.get("senha", "")

        credenciais_validas = (
            bool(senha_esperada)
            and hmac.compare_digest(usuario, usuario_esperado)
            and hmac.compare_digest(senha, senha_esperada)
        )
        if credenciais_validas:
            session.clear()
            session["admin_autenticado"] = True
            token_csrf()
            return redirect(url_for("admin.dashboard"))

        flash("Usuário ou senha inválidos.", "erro")

    return render_template("admin/login.html")


@admin_bp.post("/logout")
@admin_autenticado
def logout():
    if not csrf_valido():
        return "Requisição inválida", 400
    session.clear()
    return redirect(url_for("admin.login"))


@admin_bp.get("/")
@admin_autenticado
def dashboard():
    with conectar() as conexao:
        resumo = conexao.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM grupos WHERE ativo = 1) AS grupos_ativos,
                (SELECT COUNT(*) FROM requisicoes_api
                    WHERE date(criado_em) = date('now')) AS requisicoes_hoje,
                (SELECT COUNT(*) FROM requisicoes_api
                    WHERE date(criado_em) = date('now') AND status >= 400) AS erros_hoje,
                (SELECT COUNT(*) FROM grupos g
                    WHERE g.ativo = 1
                    AND NOT EXISTS (
                        SELECT 1 FROM requisicoes_api r WHERE r.grupo_id = g.id
                    )) AS nunca_conectaram
            """
        ).fetchone()

        grupos = conexao.execute(
            """
            SELECT
                g.id,
                g.nome,
                g.turma,
                g.ativo,
                COUNT(r.id) AS total_requisicoes,
                MIN(r.criado_em) AS primeira_requisicao,
                MAX(r.criado_em) AS ultima_requisicao,
                SUM(CASE WHEN r.status >= 400 THEN 1 ELSE 0 END) AS total_erros
            FROM grupos g
            LEFT JOIN requisicoes_api r ON r.grupo_id = g.id
            GROUP BY g.id
            ORDER BY ultima_requisicao DESC, g.nome
            """
        ).fetchall()

        metodos = conexao.execute(
            """
            SELECT metodo, COUNT(*) AS total
            FROM requisicoes_api
            GROUP BY metodo
            ORDER BY total DESC
            """
        ).fetchall()

        recentes = conexao.execute(
            """
            SELECT r.criado_em, r.metodo, r.rota, r.status, r.duracao_ms,
                   COALESCE(g.nome, 'Não identificado') AS grupo
            FROM requisicoes_api r
            LEFT JOIN grupos g ON g.id = r.grupo_id
            ORDER BY r.id DESC
            LIMIT 100
            """
        ).fetchall()

    return render_template(
        "admin/dashboard.html",
        resumo=resumo,
        grupos=grupos,
        metodos=metodos,
        recentes=recentes,
    )


@admin_bp.get("/grupos")
@admin_autenticado
def grupos():
    with conectar() as conexao:
        lista = conexao.execute(
            """
            SELECT g.id, g.nome, g.turma, g.ativo, g.criado_em,
                   t.prefixo, t.ativo AS token_ativo
            FROM grupos g
            LEFT JOIN tokens_api t
              ON t.grupo_id = g.id AND t.ativo = 1
            ORDER BY g.nome
            """
        ).fetchall()

    return render_template("admin/grupos.html", grupos=lista, novo_token=None)


@admin_bp.post("/grupos")
@admin_autenticado
def criar_grupo():
    if not csrf_valido():
        return "Requisição inválida", 400

    nome = request.form.get("nome", "").strip()
    turma = request.form.get("turma", "").strip()

    if not nome:
        flash("Informe o nome do grupo.", "erro")
        return redirect(url_for("admin.grupos"))

    token = secrets.token_urlsafe(32)
    with conectar() as conexao:
        cursor = conexao.execute(
            "INSERT INTO grupos (nome, turma, criado_em) VALUES (?, ?, ?)",
            (nome, turma or None, agora_iso()),
        )
        grupo_id = cursor.lastrowid
        conexao.execute(
            """
            INSERT INTO tokens_api
                (grupo_id, token_hash, prefixo, criado_em)
            VALUES (?, ?, ?, ?)
            """,
            (grupo_id, hash_token(token), token[:8], agora_iso()),
        )

        lista = conexao.execute(
            """
            SELECT g.id, g.nome, g.turma, g.ativo, g.criado_em,
                   t.prefixo, t.ativo AS token_ativo
            FROM grupos g
            LEFT JOIN tokens_api t
              ON t.grupo_id = g.id AND t.ativo = 1
            ORDER BY g.nome
            """
        ).fetchall()

    return render_template(
        "admin/grupos.html",
        grupos=lista,
        novo_token={"grupo": nome, "token": token},
    )


@admin_bp.post("/grupos/<int:grupo_id>/novo-token")
@admin_autenticado
def novo_token(grupo_id):
    if not csrf_valido():
        return "Requisição inválida", 400

    token = secrets.token_urlsafe(32)
    with conectar() as conexao:
        grupo = conexao.execute(
            "SELECT nome FROM grupos WHERE id = ?",
            (grupo_id,),
        ).fetchone()
        if grupo is None:
            return "Grupo não encontrado", 404

        conexao.execute(
            """
            UPDATE tokens_api
            SET ativo = 0, revogado_em = ?
            WHERE grupo_id = ? AND ativo = 1
            """,
            (agora_iso(), grupo_id),
        )
        conexao.execute(
            """
            INSERT INTO tokens_api
                (grupo_id, token_hash, prefixo, criado_em)
            VALUES (?, ?, ?, ?)
            """,
            (grupo_id, hash_token(token), token[:8], agora_iso()),
        )

        lista = conexao.execute(
            """
            SELECT g.id, g.nome, g.turma, g.ativo, g.criado_em,
                   t.prefixo, t.ativo AS token_ativo
            FROM grupos g
            LEFT JOIN tokens_api t
              ON t.grupo_id = g.id AND t.ativo = 1
            ORDER BY g.nome
            """
        ).fetchall()

    return render_template(
        "admin/grupos.html",
        grupos=lista,
        novo_token={"grupo": grupo["nome"], "token": token},
    )


@admin_bp.post("/grupos/<int:grupo_id>/alternar")
@admin_autenticado
def alternar_grupo(grupo_id):
    if not csrf_valido():
        return "Requisição inválida", 400

    with conectar() as conexao:
        conexao.execute(
            "UPDATE grupos SET ativo = CASE ativo WHEN 1 THEN 0 ELSE 1 END WHERE id = ?",
            (grupo_id,),
        )

    return redirect(url_for("admin.grupos"))
