import json
import os
import time
from itertools import combinations
from pathlib import Path
from threading import Lock, Thread
import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
ARQUIVO = Path(__file__).with_name("campeonato.json")
LOCK = Lock()
PLACAR_URL = os.getenv("PLACAR_URL", "http://127.0.0.1:5001").rstrip("/")
PLACAR_API_KEY = os.getenv("PLACAR_API_KEY", "chave-aula-123")  # Fica só no backend
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

def consultar_placar(placar_id):
    """Retorna (placar, mensagem_erro, deve_parar)."""
    try:
        resposta = requests.get(f"{PLACAR_URL}/api/placares/{placar_id}", timeout=TIMEOUT)
    except requests.RequestException as e:
        return None, f"Placar indisponível ({e.__class__.__name__}); tentando novamente", False
    if resposta.status_code == 404:
        return None, f"Placar {placar_id} não existe mais no servidor", True
    if resposta.status_code >= 500:
        return None, f"Placar respondeu {resposta.status_code}; tentando novamente", False
    if resposta.status_code != 200:
        return None, f"Resposta inesperada {resposta.status_code}", False
    return resposta.json(), None, False

def sincronizar_partida(partida, modalidade):
    placar, mensagem, parar = consultar_placar(partida["placar_id"])
    partida["ultimo_erro"] = mensagem
    if parar:
        partida["status"] = "erro_placar"
    if placar is None:
        return
    partida["placar"] = {c: placar.get(c) for c in ("status", "tempo", "etapa", "pontos_equipe_a", "pontos_equipe_b",
                                                    "faltas_equipe_a", "faltas_equipe_b", "detalhes")}
    if placar["status"] == "finalizado":
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
    return jsonify({**campeonato, "classificacao": classificacao(campeonato), "placar_url": PLACAR_URL}), 200

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
    try:
        resposta = requests.post(f"{PLACAR_URL}/api/placares", json=corpo, headers={"X-API-Key": PLACAR_API_KEY}, timeout=TIMEOUT)
    except requests.RequestException as e:
        return erro(f"Placar Eletrônico indisponível: {e.__class__.__name__}", 503)
    if resposta.status_code != 201:
        return erro(f"Placar recusou a criação ({resposta.status_code}): {resposta.text}", 502)
    placar = resposta.json()
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

if __name__ == "__main__":
    Thread(target=polling, daemon=True).start()
    # use_reloader=False evita que o modo debug inicie a thread de polling duas vezes
    app.run(host="0.0.0.0", port=int(os.getenv("PORTA", "5002")), debug=True, use_reloader=False)
