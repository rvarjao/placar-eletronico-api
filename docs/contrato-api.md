# Contrato da API — versão 1

URL base de exemplo: `http://192.168.1.100:5001/api`. Chaves JSON em snake_case.

## Campos

| Campo | Tipo | Regra |
|---|---|---|
| id | inteiro | gerado no POST e retornado nas consultas |
| nome_equipe_a, nome_equipe_b | texto | obrigatórios |
| modalidade | texto validado | futebol, futsal, basquete, volei, handebol, outro |
| status | texto validado | nao_iniciado, em_andamento, pausado, finalizado |
| tempo | inteiro | segundos >= 0; crescente ou regressivo conforme esporte |
| etapa | texto | ex.: 1º tempo, 3º quarto, 4º set |
| pontos_equipe_a, pontos_equipe_b | inteiro | >= 0 |
| faltas_equipe_a, faltas_equipe_b | inteiro | >= 0 |
| detalhes | objeto JSON | informações opcionais específicas do esporte |

## POST /placares

Entrada mínima (valores padrão para status, tempo, pontos e faltas devem ser implementados):

```json
{"nome_equipe_a":"Brasil","nome_equipe_b":"Argentina","modalidade":"futebol","etapa":"1º tempo"}
```

Resposta esperada: **201 Created**:

```json
{"id":15,"nome_equipe_a":"Brasil","nome_equipe_b":"Argentina","modalidade":"futebol","status":"nao_iniciado","tempo":0,"etapa":"1º tempo","pontos_equipe_a":0,"pontos_equipe_b":0,"faltas_equipe_a":0,"faltas_equipe_b":0,"detalhes":{}}
```

## GET /placares/{id}

Resposta esperada: **200 OK**:

```json
{"id":15,"nome_equipe_a":"Brasil","nome_equipe_b":"Argentina","modalidade":"futebol","status":"em_andamento","tempo":2520,"etapa":"2º tempo","pontos_equipe_a":2,"pontos_equipe_b":1,"faltas_equipe_a":3,"faltas_equipe_b":5,"detalhes":{}}
```

Se não existir, responder **404 Not Found**, por exemplo `{"erro":"placar_nao_encontrado"}`.

## PATCH /placares/{id}

Usada pelo operador do placar (com autorização). Enviar apenas campos alterados:

```json
{"pontos_equipe_a":3,"tempo":2700,"etapa":"2º tempo"}
```

Resposta esperada: **200 OK**, com objeto atualizado. Não permitir alteração do ID.

## Exemplo específico: vôlei

```json
{"id":20,"nome_equipe_a":"Brasil","nome_equipe_b":"Argentina","modalidade":"volei","status":"em_andamento","tempo":0,"etapa":"4º set","pontos_equipe_a":24,"pontos_equipe_b":22,"faltas_equipe_a":0,"faltas_equipe_b":0,"detalhes":{"sets_equipe_a":2,"sets_equipe_b":1}}
```

No vôlei, os campos `pontos_equipe_*` representam pontos do set atual; os sets vencidos estão em `detalhes`.

## Erros

- 201: criado; 200: consulta/atualização.
- 400 ou 422: entrada inválida; 404: não encontrado.
- 401/403: atualização não autorizada.
- 500: erro inesperado; 503: indisponibilidade de dependência.

Cabe à turma implementar validações, persistência, tratamento de erros e autenticação. **O esqueleto retorna 501 intencionalmente.**
