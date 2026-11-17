# Placar Eletrônico — API publicada

Aplicação Flask do Projeto Interclasse: API de placares, painel administrativo, landing page e integração com Supabase. A implementação de produção está em [`app/`](app/). As interfaces de Campeonato e Placar Eletrônico ficam em [`exemplos/`](exemplos/) e são montadas no mesmo servidor.

## Páginas e API

- `/`: landing page das equipes.
- `/monitor`: monitor público; `/integracao`: guia de integração.
- `/admin/login`: acesso administrativo; `/admin`: painel.
- `/exemplos/campeonato/` e `/exemplos/placar-eletronico/`: interfaces demonstrativas.
- `/api/placares`: API autenticada por token de grupo.

## Execução local

1. Execute [`app/supabase/schema.sql`](app/supabase/schema.sql) no SQL Editor do Supabase.
2. Copie `.env.example` para `.env` e preencha as credenciais somente no servidor.
3. Instale as dependências com `pip install -r requirements.txt`.
4. Carregue o ambiente e execute `python run.py` (porta 5000), ou use `docker compose up --build` (porta 5001 no host).

Consulte [configuração, migração e endpoints](docs/api-publicada.md), [integração dos exemplos](exemplos/README.md) e [deploy no PythonAnywhere](docs/deploy-pythonanywhere.md).
