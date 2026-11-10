"""Importação pontual da persistência antiga para o Supabase.

Execute no servidor que possui os arquivos originais, após executar schema.sql.
Não apaga os arquivos de origem: verifique os dados antes de removê-los.
"""
import json
import sqlite3
from pathlib import Path

from db_supabase import db

ROOT = Path(__file__).resolve().parents[1]


def importar_registros(tabela, registros):
    if not registros:
        return 0
    for linha in registros:
        db().request(
            "POST", tabela, params={"on_conflict": "id"}, data=linha,
            prefer="resolution=merge-duplicates,return=minimal",
        )
    return len(registros)


def importar_sqlite():
    caminho = Path(__file__).with_name("monitoramento.db")
    if not caminho.exists():
        print("SQLite: nenhum arquivo encontrado")
        return
    conexao = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
    conexao.row_factory = sqlite3.Row
    try:
        for tabela in ("grupos", "tokens_api", "requisicoes_api"):
            linhas = [dict(linha) for linha in conexao.execute(f"SELECT * FROM {tabela}")]
            print(f"{tabela}: {importar_registros(tabela, linhas)} registros")
    finally:
        conexao.close()


def importar_json(caminho, chave=None):
    if not caminho.exists():
        return
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    if chave:
        db().state_set(chave, dados)
        print(f"{chave}: importado")
    else:
        print(f"placares: {importar_registros('placares', dados)} registros")


def main():
    importar_json(Path(__file__).with_name("placares.json"))
    importar_sqlite()
    importar_json(ROOT / "campeonato" / "campeonato.json", "campeonato_estado")
    importar_json(ROOT / "campeonato" / "conexao_api.json", "campeonato_conexao")
    importar_json(ROOT / "placar-eletronico" / "estado_local.json", "placar_eletronico_estado")
    importar_json(ROOT / "placar-eletronico" / "conexao_api.json", "placar_eletronico_conexao")
    db().rpc("sincronizar_ids_api_completa")
    print("Importação concluída. Confira os dados no Supabase antes de ativar a nova aplicação.")


if __name__ == "__main__":
    main()
