# Contrato da API publicada

Base: `/api/placares`. Todas as operações exigem `Authorization: Bearer TOKEN_DO_GRUPO`. Opcionalmente, o servidor aceita `X-API-Key` quando `API_KEY` está configurada.

## Placar

Cada placar contém `id`, `nome_equipe_a`, `nome_equipe_b`, `modalidade`, `status`, `pontos_a`, `pontos_b` e `tempo_partida`. `id` é gerado pelo Supabase. Os pontos e o tempo são inteiros não negativos; o tempo é medido em segundos. Status válidos: `aguardando`, `em_andamento`, `encerrado`.

## Operações

| Método e caminho | Comportamento |
| --- | --- |
| `GET /api/placares` | Lista os placares; 200. |
| `GET /api/placares/{id}` | Consulta um placar; 200 ou 404. |
| `POST /api/placares/criar` | Cria com `nome_equipe_a`, `nome_equipe_b` e `modalidade` não vazios; define status `aguardando` e números zero; 201 com `Location`. |
| `PUT /api/placares/{id}` | Substitui os campos do placar; exige os três textos, status, pontos e tempo; 200 ou 404. |
| `PATCH /api/placares/{id}` | Altera somente `pontos_a`, `pontos_b`, `status` e/ou `tempo_partida`; 200 ou 404. |
| `DELETE /api/placares/{id}` | Exclui o placar; 204 ou 404. |

Dados inválidos retornam 400; token ausente ou inválido retorna 401; falha de persistência no Supabase retorna 503. Os exemplos de Campeonato e Placar Eletrônico armazenam informações auxiliares, como etapa e faltas, em `estado_aplicacoes` no Supabase.

Cada placar criado recebe o `grupo_id` do token autenticado. Apenas esse grupo pode alterar ou excluir o placar; outro grupo recebe 403. Para chamadas do navegador, a origem deve corresponder à origem cadastrada para o grupo. O preflight CORS aceita apenas origens cadastradas e métodos/cabeçalhos da API.

```bash
curl -X POST https://rvarjao.pythonanywhere.com/api/placares/criar \
  -H 'Authorization: Bearer TOKEN_DO_GRUPO' \
  -H 'Content-Type: application/json' \
  -d '{"nome_equipe_a":"Brasil","nome_equipe_b":"Argentina","modalidade":"futsal"}'
```
