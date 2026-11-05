# Exemplo — Gerenciador de Campeonato (porta 5002)

Cadastra equipes, gera partidas, cria placares por API HTTP, acompanha os resultados por polling e monta a classificação. Os dados locais do campeonato ficam em `campeonato.json`.

O exemplo aceita dois modos:

- **API publicada** — usa o token do grupo em `Authorization: Bearer`.
- **Placar local** — mantém a compatibilidade com `X-API-Key` e o exemplo da porta 5001.

## Usar com a API publicada

No Linux ou macOS:

```bash
cd exemplos/campeonato
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export PLACAR_URL="https://rvarjao.pythonanywhere.com"
export PLACAR_TOKEN="COLE_AQUI_O_TOKEN_DO_GRUPO"

python app.py
```

No PowerShell:

```powershell
cd exemplos/campeonato
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:PLACAR_URL = "https://rvarjao.pythonanywhere.com"
$env:PLACAR_TOKEN = "COLE_AQUI_O_TOKEN_DO_GRUPO"

python app.py
```

Abra `http://127.0.0.1:5002`.

Não grave o token no código nem envie o token ao GitHub.

## Usar com o placar local

Inicie primeiro o [Placar Eletrônico](../placar-eletronico/README.md) na porta 5001. Depois execute:

```bash
cd exemplos/campeonato
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Sem `PLACAR_TOKEN`, o exemplo usa `http://127.0.0.1:5001`, a rota local `POST /api/placares` e `X-API-Key`.

## Configuração

| Variável | Padrão | Uso |
|---|---|---|
| `PLACAR_URL` | `http://127.0.0.1:5001` | endereço da API |
| `PLACAR_TOKEN` | vazio | token do grupo para a API publicada |
| `PLACAR_API_KEY` | `chave-aula-123` | chave didática usada apenas no modo local |
| `PLACAR_CREATE_PATH` | automático | `/api/placares/criar` com token ou `/api/placares` no modo local |
| `INTERVALO_POLLING` | `5` | segundos entre consultas |
| `PORTA` | `5002` | porta deste sistema |

## Fluxo com a API publicada

1. Gere o campeonato e as partidas.
2. Clique em **Criar placar**.
3. O backend envia `POST {PLACAR_URL}/api/placares/criar` com o Bearer token.
4. O identificador retornado fica associado à partida.
5. O backend consulta `GET /api/placares/<id>` periodicamente.
6. Quando o status passa para `encerrado`, o resultado entra na classificação.

Todas as chamadas passam pelo backend Flask. O token não é enviado ao navegador.

## API deste sistema

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/campeonato` | campeonato, partidas e classificação |
| POST | `/api/campeonato` | gera as partidas e substitui o campeonato atual |
| POST | `/api/partidas/<id>/iniciar` | cria o placar remoto |
| POST | `/api/partidas/<id>/sincronizar` | consulta o placar imediatamente |

## Falhas tratadas

- timeout ou servidor indisponível
- respostas 401 por token ausente ou inválido
- placar inexistente
- tentativa de criar dois placares para a mesma partida
- respostas inesperadas da API

## Teste sugerido

Use primeiro um grupo de teste. Gere duas equipes, crie um placar e confira no painel administrativo:

- grupo identificado
- requisição `POST`
- resposta `201`
- consultas `GET`
- contagem total de requisições
