# API completa — Supabase (PostgreSQL)

A API Flask, o painel administrativo e os exemplos integrados (Campeonato e Placar Eletrônico) agora persistem dados no **Supabase**. Não utilizam mais arquivos JSON ou SQLite para persistência. As requisições e respostas HTTP continuam em formato JSON; o estado auxiliar é salvo na coluna PostgreSQL `jsonb` da tabela `estado_aplicacoes`.

## 1. Criar tabelas

No Supabase Dashboard → SQL Editor, execute [supabase/schema.sql](supabase/schema.sql).

Tabelas:
- `placares`: placares e cronômetro;
- `grupos`: grupos de alunos (nome, turma, descrição do projeto, URL e integrantes);
- `tokens_api`: hashes dos tokens;
- `requisicoes_api`: monitoramento, com `placar_id` opcional;
- `estado_aplicacoes`: estado do Campeonato, detalhes adicionais do Placar e configuração de conexão.

Todas possuem RLS habilitado e acesso negado a `anon` e `authenticated`. A API Flask usa credencial administrativa somente no servidor. **Nunca inclua a chave secreta no HTML, JavaScript, Git ou GitHub Pages.**

## 2. Variáveis de ambiente (PythonAnywhere ou local)

```bash
export SUPABASE_URL="https://SEU-PROJETO.supabase.co"
export SUPABASE_SECRET_KEY="SUA_CHAVE_PRIVADA_DE_BACKEND"
export SECRET_KEY="uma-chave-aleatoria-longa-para-flask"
# Opcional: chave publicável usada apenas no login do Supabase Auth
# (se omitida, o login usa a SUPABASE_SECRET_KEY no servidor)
export SUPABASE_PUBLISHABLE_KEY="sb_publishable_..."
# Opcional: restringe o painel a estes e-mails (separados por vírgula)
# export ADMIN_EMAILS="professor@escola.br"
# Opcional, apenas para clientes antigos. Prefira tokens por grupo:
# export API_KEY="chave-legada"
```

### Login da área administrativa

O acesso a `/admin` usa os **usuários do Supabase Auth**: entre com o mesmo e-mail e senha cadastrados em Dashboard → Authentication → Users. A senha é validada pelo Supabase no servidor Flask; o navegador nunca recebe chaves. `ADMIN_USERNAME` e `ADMIN_PASSWORD` não são mais utilizados.

**Importante:** qualquer usuário válido do projeto entra no painel. Desative o cadastro público (Authentication → Sign In / Providers → *Allow new users to sign up*) ou defina `ADMIN_EMAILS`.

Compatível também com `SUPABASE_SERVICE_ROLE_KEY` (chave JWT legada), caso ainda utilize esse formato. A chave deve ficar no ambiente do PythonAnywhere/WSGI; **não** na página de configuração dos alunos.

Instale as dependências e execute:

```bash
cd exemplos/api-completa
pip install -r requirements.txt
python app.py
```

## 3. Migração dos dados existentes (ANTES de publicar)

No servidor que contém os dados antigos (`monitoramento.db`, `placares.json`, `campeonato.json`, `estado_local.json` e arquivos de conexão), depois de executar o esquema SQL e configurar as variáveis:

```bash
cd exemplos/api-completa
python migrar_dados_legados.py
```

Faça um **backup antes** e verifique os registros no Supabase. O importador lê os arquivos antigos apenas uma vez para transferir dados; ele **não apaga os arquivos**. Não ative a nova versão sem importar os dados do servidor atual, pois os tokens e placares anteriores não aparecerão no Supabase até a importação. Depois de conferir a integridade, os arquivos antigos podem ser arquivados fora da aplicação. Não execute essa rotina enquanto houver escritas no sistema antigo.

## 4. Monitoramento e placar_id

O registro da requisição inclui `grupo_id`, `metodo`, `rota`, `status`, `duracao_ms` e `placar_id`:
- GET de lista ou erro sem placar existente: `placar_id = NULL`;
- GET de placar, PUT e PATCH bem-sucedidos: ID do placar;
- POST de criação bem-sucedido: ID gerado pelo Supabase;
- DELETE: `placar_id = NULL`, porque o placar já foi excluído e a FK usa `ON DELETE SET NULL`.

## 5. Endpoints

- `GET /api/placares`
- `GET /api/placares/<id>`
- `POST /api/placares/criar`
- `PUT /api/placares/<id>`
- `PATCH /api/placares/<id>`
- `DELETE /api/placares/<id>`

Use `Authorization: Bearer TOKEN_DO_GRUPO`. Opcionalmente, habilite `API_KEY` para clientes legados com `X-API-Key`. O Postman disponibiliza uma coleção didática em `postman_collection.json` (não utilizada para persistência).

A interface de Campeonato e Placar Eletrônico continua em Flask; alterações de estado são enviadas ao Supabase. O deploy de produção depende da configuração e execução do SQL no projeto Supabase; a criação das tabelas não é automática ao inicializar o Flask.
