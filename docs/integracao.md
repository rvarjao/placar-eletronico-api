# Integração entre os sistemas

O Gerenciador de Campeonato cria um placar em `POST /api/placares/criar`, guarda o `id` retornado e consulta `GET /api/placares/{id}` aproximadamente a cada 5 segundos. O operador atualiza pontuação, status e tempo por `PATCH /api/placares/{id}`. Ao receber `status=encerrado`, o Campeonato registra o resultado e interrompe as consultas.

As chamadas usam o token de um grupo no cabeçalho `Authorization: Bearer`. Nas interfaces de exemplo, o token fica no backend, nunca no navegador. Os dois clientes podem rodar separados ou montados no servidor principal em `/exemplos/campeonato/` e `/exemplos/placar-eletronico/`.

Em timeout ou falha 5xx, o cliente avisa e tenta novamente. Em 404, trata o ID como desconhecido sem criar automaticamente outro placar. A [API publicada](contrato-api.md) define campos e respostas.
