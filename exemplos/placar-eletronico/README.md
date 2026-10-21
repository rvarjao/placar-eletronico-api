# Exemplo — Placar Eletrônico (porta 5001)

Uma das duas pontas do projeto. Expõe a API do [contrato](../../docs/contrato-api.md), controla a partida (pontos, faltas, etapa, cronômetro, status) e oferece telas de operador e de telão. Persistência em `placares.json` (criado automaticamente).

Funciona junto com o [Gerenciador de Campeonato](../campeonato/README.md).

## Executar

```bash
cd exemplos/placar-eletronico
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Variáveis opcionais: `API_KEY` (padrão `chave-aula-123`) e `PORTA` (padrão `5001`). O servidor escuta em `0.0.0.0`, então outros computadores da rede acessam por `http://<ip-da-máquina>:5001`.

## Telas

| URL | Para quê |
|---|---|
| `/` | lista de placares |
| `/operador/<id>` | controles do operador (pede a API Key, guardada só na aba) |
| `/placar/<id>` | telão público, atualiza a cada 1 s |

## API

| Método | Rota | Auth | Respostas |
|---|---|---|---|
| GET | `/api/placares` | — | 200 |
| GET | `/api/placares/<id>` | — | 200, 404 |
| POST | `/api/placares` | `X-API-Key` | 201, 400, 401 |
| PATCH | `/api/placares/<id>` | `X-API-Key` | 200, 400, 401, 404, 409 |

- `modalidade`: futebol, futsal, basquete, volei, handebol, outro.
- `status`: nao_iniciado → em_andamento ⇄ pausado → finalizado. Depois de `finalizado` o PATCH responde **409**.
- PATCH aceita só `status`, `etapa`, `tempo`, `pontos_equipe_*`, `faltas_equipe_*` e `detalhes`; `id`, nomes e modalidade não podem ser alterados.

## Cronômetro

O cronômetro roda **no servidor**: ao entrar em `em_andamento` é guardado o instante de início (campo interno `_inicio`, nunca devolvido pela API) e cada GET calcula o `tempo` atual. Ao pausar ou finalizar, o valor é congelado. Futebol/futsal/handebol contam para cima; basquete começa em 600 s (10 min) e conta para baixo. Assim, o telão e o Campeonato veem o mesmo tempo mesmo que o operador feche a página.

## Especialização por modalidade

A tela do operador é uma só; muda apenas o necessário:
- **basquete**: botões +1, +2, +3 e relógio regressivo;
- **vôlei**: `detalhes` guarda `sets_equipe_a`/`sets_equipe_b`; o botão “Fechar set” soma o set ao vencedor, zera os pontos e avança a etapa.

**Atenção:** `chave-aula-123` é didática. O JSON em arquivo não suporta vários processos; no projeto real use o PostgreSQL do Supabase.
