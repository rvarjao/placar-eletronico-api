"""CORS para as rotas da API autenticadas por token."""
from urllib.parse import urlsplit

from flask import current_app, jsonify, make_response, request
from werkzeug.exceptions import MethodNotAllowed, NotFound

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


def preflight():
    """Valida o método e os cabeçalhos solicitados pelo navegador."""
    metodo = request.headers.get("Access-Control-Request-Method", "").upper()
    headers = {h.strip().lower() for h in request.headers.get("Access-Control-Request-Headers", "").split(",") if h.strip()}
    if metodo not in METODOS or not headers <= HEADERS:
        return jsonify(erro="Método ou cabeçalhos não autorizados"), 403
    try:
        regra, _ = current_app.url_map.bind_to_environ(request.environ).match(
            method=metodo, return_rule=True,
        )
    except (MethodNotAllowed, NotFound):
        return jsonify(erro="Método ou cabeçalhos não autorizados"), 403
    resposta = make_response("", 204)
    resposta.headers["Access-Control-Allow-Methods"] = ", ".join(sorted(regra.methods & METODOS))
    resposta.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    resposta.headers["Access-Control-Max-Age"] = "300"
    resposta.vary.add("Access-Control-Request-Method")
    resposta.vary.add("Access-Control-Request-Headers")
    return resposta


def aplicar_cors(resposta):
    resposta.headers["Access-Control-Allow-Origin"] = "*"
    resposta.headers["Access-Control-Expose-Headers"] = "Location"
    return resposta
