# Exemplo completo — API REST de placares

Material didático isolado do projeto principal. Flask, CRUD, persistência em arquivo JSON, autenticação simples e Postman.

## Executar

```bash
cd exemplos/api-completa
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```

API: `http://127.0.0.1:5000`. Importe `postman_collection.json` no Postman.

## Sequência da aula

1. GET /api/placares — listar (200)
2. POST /api/placares — criar (201)
3. GET /api/placares/1 — consultar (200)
4. PATCH /api/placares/1 — alterar pontos (200)
5. PUT /api/placares/1 — substituir (200)
6. DELETE /api/placares/1 — excluir (204)
7. GET /api/placares/1 — inexistente (404)
8. POST sem X-API-Key — não autenticado (401)
9. POST com dados inválidos — erro de validação (400)

O Postman usa as variáveis `base_url`, `api_key` e `placar_id`.

**Atenção:** `chave-aula-123` é uma chave pública e didática, nunca de produção. Configure `API_KEY` por variável de ambiente em sistemas reais. O JSON é apenas para aprendizado, sem suporte a concorrência entre processos.
