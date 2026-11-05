# Exemplo — Placar Eletrônico (porta 5001)

Telas de operador e de telão para os placares da [API publicada](../api-completa/README.md). O sistema usa o token de um grupo para ler e gravar os placares na API; quem cria as partidas costuma ser o [Gerenciador de Campeonato](../campeonato/README.md).

Os dados que a API não guarda (etapa, faltas, sets do vôlei e a pausa do cronômetro) ficam neste sistema, em `estado_local.json` (criado automaticamente).

## Conectar à API

No servidor publicado (`/exemplos/placar-eletronico/`), o administrador informa o token em **Configurar Placar Eletrônico** (`/configuracao`). Veja o passo a passo em [exemplos](../README.md#configurar-o-token-pela-tela). Sem token, as telas avisam que a conexão não está configurada.

## Executar na sua máquina

```bash
cd exemplos/placar-eletronico
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abra `http://127.0.0.1:5001/configuracao` e informe o endereço da API (padrão `http://127.0.0.1:5000`, a API completa rodando local) e o token do grupo. Variáveis opcionais: `PLACAR_URL` e `PLACAR_TOKEN` (valores iniciais), `API_KEY` (padrão `chave-aula-123`) e `PORTA` (padrão `5001`). O servidor escuta em `0.0.0.0`, então outros computadores da rede acessam por `http://<ip-da-máquina>:5001`.

## Telas

| URL | Para quê |
|---|---|
| `/` | lista de placares da API |
| `/operador/<id>` | controles do operador (pede a API Key, guardada só na aba) |
| `/placar/<id>` | telão público, atualiza a cada 1 s |
| `/configuracao` | token e endereço da API (só o administrador no servidor publicado) |

## API deste sistema

As telas usam estas rotas, que repassam o pedido à API publicada com o token configurado:

| Método | Rota | Auth | Respostas |
|---|---|---|---|
| GET | `/api/placares` | — | 200, 502, 503 |
| GET | `/api/placares/<id>` | — | 200, 404, 502, 503 |
| POST | `/api/placares` | `X-API-Key` | 201, 400, 401, 502, 503 |
| PATCH | `/api/placares/<id>` | `X-API-Key` | 200, 400, 401, 404, 409, 502, 503 |

- `modalidade`: futebol, futsal, basquete, volei, handebol, outro.
- `status`: nao_iniciado → em_andamento ⇄ pausado → finalizado. Na API isso vira `aguardando`, `em_andamento` (também quando pausado) e `encerrado`. Depois de `finalizado` o PATCH responde **409**.
- PATCH aceita só `status`, `etapa`, `tempo`, `pontos_equipe_*`, `faltas_equipe_*` e `detalhes`; `id`, nomes e modalidade não podem ser alterados.
- **503**: token não configurado ou API fora do ar. **502**: a API recusou o token ou respondeu algo inesperado.

## O que vai para a API

| Na API (`/api/placares`) | Neste sistema |
|---|---|
| `nome_equipe_a/b`, `modalidade` | iguais |
| `pontos_a`, `pontos_b` | `pontos_equipe_a`, `pontos_equipe_b` |
| `status` | `status` (com `pausado`) |
| `tempo_partida` (segundos decorridos) | `tempo` |
| — | `etapa`, `faltas_equipe_*`, `detalhes`: só no `estado_local.json` |

## Cronômetro

O tempo corrido é calculado **neste sistema**: ao entrar em `em_andamento` guarda-se o instante de início e cada consulta soma o tempo corrido ao `tempo_partida` da API. Ao pausar, finalizar ou alterar o placar, o valor é congelado e enviado à API. Futebol/futsal/handebol contam para cima; o basquete mostra 600 s (10 min) menos o tempo decorrido. Assim, o telão e o Campeonato veem o mesmo tempo mesmo que o operador feche a página.

## Especialização por modalidade

A tela do operador é uma só; muda apenas o necessário:
- **basquete**: botões +1, +2, +3 e relógio regressivo;
- **vôlei**: `detalhes` guarda `sets_equipe_a`/`sets_equipe_b`; o botão “Fechar set” soma o set ao vencedor, zera os pontos e avança a etapa.

**Atenção:** `chave-aula-123` é didática. O JSON em arquivo não suporta vários processos; no projeto real use o PostgreSQL do Supabase.
