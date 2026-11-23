"""CORS para as rotas da API autenticadas por token."""
from flask import current_app, jsonify, make_response, request
from werkzeug.exceptions import MethodNotAllowed, NotFound

METODOS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"}
HEADERS = {"authorization", "content-type"}


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
