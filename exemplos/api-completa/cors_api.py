"""CORS explícito para a API; Origin é uma restrição adicional, não autenticação."""
from urllib.parse import urlsplit

from flask import request, g, jsonify
from db_supabase import db

METODOS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"}
HEADERS = {"authorization", "content-type"}


def normalizar_origem(valor):
    """Aceita uma origem HTTP(S), sem caminho, credenciais, query ou fragmento."""
    if not isinstance(valor, str) or not valor or any(c.isspace() for c in valor) or "\\" in valor:
        raise ValueError("Informe uma origem HTTP(S) válida.")
    try:
        p = urlsplit(valor)
        porta = p.port
        if (p.scheme not in ("http", "https") or not p.hostname or
                p.username is not None or p.password is not None or
                p.path not in ("", "/") or "?" in valor or "#" in valor or
                not p.netloc or p.hostname.endswith(".")):
            raise ValueError
        host = p.hostname.lower()
        if ":" in host:
            host = "[" + host + "]"
        if porta is not None and porta != (443 if p.scheme == "https" else 80):
            host += ":" + str(porta)
        return p.scheme + "://" + host
    except ValueError:
        raise ValueError("Informe uma origem como https://aluno.github.io, sem caminho.") from None


def origem_requisicao():
    valor = request.headers.get("Origin")
    if valor is None:
        return None
    try:
        origem = normalizar_origem(valor)
        # Origin serializado pelo navegador não inclui barra ou porta padrão.
        return origem if valor == origem else ""
    except ValueError:
        return ""


def origem_cadastrada(origem):
    return bool(origem and db().one("grupos", columns="id",
                filters={"origem_permitida": f"eq.{origem}", "ativo": "eq.1"}))


def preflight(origem):
    """OPTIONS não transporta Bearer. Autoriza origem global; chamada real valida grupo."""
    metodo = request.headers.get("Access-Control-Request-Method", "").upper()
    headers = {h.strip().lower() for h in request.headers.get("Access-Control-Request-Headers", "").split(",") if h.strip()}
    if (not origem or metodo not in METODOS or not request.url_rule
            or metodo not in request.url_rule.methods or not headers <= HEADERS
            or not origem_cadastrada(origem)):
        return jsonify(erro="Origem, método ou cabeçalhos não autorizados"), 403
    g.cors_origem = origem
    from flask import make_response
    resposta = make_response("", 204)
    resposta.headers["Access-Control-Allow-Methods"] = ", ".join(sorted(request.url_rule.methods & METODOS))
    resposta.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    resposta.headers["Access-Control-Max-Age"] = "300"
    resposta.vary.add("Access-Control-Request-Method")
    resposta.vary.add("Access-Control-Request-Headers")
    return resposta


def validar_origem_grupo(grupo, origem):
    permitida = grupo.get("origem_permitida")
    restrito = bool(grupo.get("restringir_origem"))
    if origem is None:
        return not restrito
    if not origem:
        return False
    if permitida and origem == permitida:
        return True
    # Sem restrição, chamadas locais de mesma origem continuam funcionando.
    if not restrito and origem == request.host_url.rstrip("/"):
        return True
    return False


def aplicar_cors(resposta):
    resposta.vary.add("Origin")
    origem = getattr(g, "cors_origem", None)
    if origem:
        resposta.headers["Access-Control-Allow-Origin"] = origem
        resposta.headers["Access-Control-Expose-Headers"] = "Location"
    return resposta
