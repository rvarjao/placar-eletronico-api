# Integração entre os sistemas

1. Campeonatos cadastra a partida e envia **POST** a `/api/placares`.
2. Recebe **201** com `id` e armazena esse valor como `placar_id` em sua própria partida.
3. Enquanto a partida estiver em acompanhamento, consulta **GET** `/api/placares/{placar_id}` aproximadamente a cada **5 segundos**.
4. Atualiza a tela com pontuação, faltas, etapa, tempo e `detalhes`.
5. Ao receber `status=finalizado`, interrompe polling e registra o resultado final.
6. Em timeout ou falhas 5xx, exibe mensagem e tenta novamente depois, sem criar automaticamente outro placar. Em 404, trata o ID desconhecido.

Exemplo de criação (URL ilustrativa):

```bash
curl -X POST http://192.168.1.100:5001/api/placares \
  -H 'Content-Type: application/json' \
  -d '{"nome_equipe_a":"Brasil","nome_equipe_b":"Argentina","modalidade":"futebol","etapa":"1º tempo"}'
```

Consulta:

```bash
curl http://192.168.1.100:5001/api/placares/15
```

A integração é didaticamente por **polling**, não webhook ou WebSocket. Preferir chamadas do backend de Campeonatos; se o navegador consultar diretamente a API, configurar CORS para origens permitidas. O Supabase é acessado exclusivamente pelos respectivos backends.

## Teste integrado

Criar partida -> registrar ID -> alterar pontuação via operador -> verificar GET -> finalizar -> conferir interrupção de consultas. Simular falhas de rede e validar comportamento.
