# Exemplo — Gerenciador de Campeonato (porta 5002)

A outra ponta do projeto. Cadastra equipes, gera as partidas (todos contra todos), cria um placar no [Placar Eletrônico](../placar-eletronico/README.md) para cada partida, acompanha por **polling** e monta a classificação com os resultados. Persistência em `campeonato.json` (criado automaticamente). Este sistema **nunca acessa os dados do placar diretamente**, apenas a API HTTP.

## Executar

Com o Placar Eletrônico já rodando na porta 5001:

```bash
cd exemplos/campeonato
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abra `http://127.0.0.1:5002`.

| Variável | Padrão | Uso |
|---|---|---|
| `PLACAR_URL` | `http://127.0.0.1:5001` | endereço do Placar (ex.: `http://192.168.1.100:5001`) |
| `PLACAR_API_KEY` | `chave-aula-123` | enviada no `X-API-Key` do POST; fica só no backend |
| `INTERVALO_POLLING` | `5` | segundos entre consultas |
| `PORTA` | `5002` | porta deste sistema |

## Fluxo

1. **Gerar partidas**: informe nome, modalidade e equipes → `POST /api/campeonato`.
2. **Criar placar** numa partida → o backend faz `POST {PLACAR_URL}/api/placares`, recebe **201** e guarda o `placar_id`. A partida passa a `em_acompanhamento`.
3. Opere a partida pelo link “operar” (abre a tela do Placar).
4. Uma thread de fundo faz `GET /api/placares/{placar_id}` a cada `INTERVALO_POLLING` segundos, só para partidas em acompanhamento.
5. Ao receber `status=finalizado`, registra o resultado, marca a partida como `encerrada` e **para de consultá-la**. A classificação é recalculada.

## API deste sistema

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/campeonato` | campeonato, partidas e classificação |
| POST | `/api/campeonato` | `{"nome", "modalidade", "equipes": [...]}` gera as partidas (substitui o atual) |
| POST | `/api/partidas/<id>/iniciar` | cria o placar remoto (409 se já existe; 503 se o Placar estiver fora) |
| POST | `/api/partidas/<id>/sincronizar` | consulta o placar imediatamente |

## Falhas tratadas

- Placar fora do ar / timeout / 5xx: registra `ultimo_erro` e tenta de novo no próximo ciclo — **não** cria outro placar.
- 404 no placar: a partida vai para `erro_placar` e o polling para.
- Criar placar duas vezes para a mesma partida: 409.

## Classificação

Vitória 3, empate 1, derrota 0; desempate por vitórias, saldo e pontos marcados. No vôlei o resultado considera os **sets** vencidos.

## Teste integrado sugerido

Gerar partidas → criar placar → alterar pontos no operador → ver a tela do Campeonato atualizar → finalizar → conferir que o resultado entrou na classificação. Depois pare o Placar (Ctrl+C) e veja a mensagem de erro e a retomada quando ele voltar.
