"""Monitor público somente leitura; não participa dos logs da API dos alunos."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, render_template
from db_supabase import db

monitor_bp = Blueprint("monitor", __name__)
CAMPOS_PLACAR = "id,modalidade,nome_equipe_a,nome_equipe_b,status,pontos_a,pontos_b,tempo_partida"

def instante(valor):
    return datetime.fromisoformat(valor.replace("Z", "+00:00")).astimezone(timezone.utc)

def montar_dados():
    banco = db()
    agora = datetime.now(timezone.utc)
    hoje = agora.astimezone(ZoneInfo("America/Sao_Paulo")).date()
    grupos = banco.all("grupos", columns="id,nome,ativo", filters={"publico": "eq.1"}, order="id.asc")
    placares = banco.all("placares", columns=CAMPOS_PLACAR, order="id.desc")
    logs = banco.all("requisicoes_api", columns="id,grupo_id,placar_id,metodo,status,criado_em", order="id.asc")
    nomes = {g["id"]: g["nome"] for g in grupos}
    habilitados = {g["id"] for g in grupos if g["ativo"] == 1}
    ultimos, alteracoes, donos, atividade = {}, {}, {}, {}
    contagem, erros, metodos, criados = Counter(), Counter(), Counter(), Counter()
    total_hoje = erros_hoje = 0
    for r in logs:
        grupo, placar = r["grupo_id"], r["placar_id"]
        # Descobrir o criador mesmo quando ele estiver privado ou desabilitado.
        if placar is not None and r["metodo"] == "POST" and r["status"] == 201:
            donos.setdefault(placar, grupo)
        if grupo not in nomes:
            continue
        t = instante(r["criado_em"])
        contagem[grupo] += 1
        metodos[r["metodo"]] += 1
        erro = r["status"] >= 400
        erros[grupo] += int(erro)
        if t.astimezone(ZoneInfo("America/Sao_Paulo")).date() == hoje:
            total_hoje += 1
            erros_hoje += int(erro)
        if 200 <= r["status"] < 300:
            ultimos[grupo] = max(ultimos.get(grupo, t), t)
            if placar is not None:
                atividade[placar] = max(atividade.get(placar, t), t)
                if r["metodo"] in ("POST", "PATCH", "PUT"):
                    alteracoes[placar] = max(alteracoes.get(placar, t), t)
    def iso(t):
        return t.isoformat() if t else None
    def recente(t):
        return t is not None and agora - t <= timedelta(minutes=5)
    # Negar por padrão: sem criador público identificado, não publicar a partida.
    placares = [p for p in placares if donos.get(p["id"]) in nomes]
    for p in placares:
        dono = donos.get(p["id"])
        if dono is not None:
            criados[dono] += 1
        p.update(grupo=nomes.get(dono, "Não identificado"),
                 ultima_comunicacao=iso(atividade.get(p["id"])),
                 ultima_escrita=iso(alteracoes.get(p["id"])))
    # Identificadores públicos neutros: não expor nomes de estudantes nos indicadores.
    # Os nomes cadastrados são os mesmos que já aparecem na landing page pública.
    for g in grupos:
        i = g["id"]
        t = ultimos.get(i)
        g.update(ultima_comunicacao=iso(t), total_requisicoes=contagem[i],
                 total_erros=erros[i], placares=criados[i],
                 situacao=("Desabilitado" if i not in habilitados else
                           "Ativo" if recente(t) else ("Sem comunicação recente" if t else "Sem comunicação bem-sucedida")))
    return {"placares": placares, "grupos": grupos, "metodos": dict(metodos),
            "resumo": {"placares": len(placares),
                       "andamento": sum(p["status"] == "em_andamento" for p in placares),
                       "encerrados": sum(p["status"] == "encerrado" for p in placares),
                       "sem_comunicacao": sum(p["status"] != "encerrado" and not recente(atividade.get(p["id"])) for p in placares),
                       "grupos_ativos": sum(recente(t) for i, t in ultimos.items() if i in habilitados),
                       "total_grupos": len(grupos), "requisicoes_hoje": total_hoje,
                       "erros_hoje": erros_hoje},
            "atualizado_em": iso(agora)}

@monitor_bp.get("/monitor")
def pagina():
    return render_template("monitor.html")

@monitor_bp.get("/monitor/dados")
def dados():
    resposta = jsonify(montar_dados())
    # Não manter resultados públicos antigos após mudança de visibilidade.
    resposta.headers["Cache-Control"] = "no-store"
    return resposta
