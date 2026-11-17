# Deploy no PythonAnywhere

O repositório deve estar clonado no PythonAnywhere, com o virtualenv apontado para o web app. Instale as dependências a partir da raiz do repositório: `pip install -r requirements.txt`. Mantenha `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `SECRET_KEY` e `DEPLOY_TOKEN` no ambiente do web app/WSGI, fora do Git.

## Ajuste único para esta migração

Antes do primeiro reload depois da mudança de `exemplos/api-completa` para `app/`:

1. No arquivo WSGI do web app, substitua o caminho antigo por **a raiz do repositório** e importe o novo ponto de entrada:

   ```python
   import sys
   sys.path.insert(0, "/home/rvarjao/placar-eletronico-api")  # ajuste ao caminho real do clone
   from wsgi import application
   ```

2. Na aba **Web > Static files**, atualize qualquer mapeamento `/static/` que aponte para `exemplos/api-completa/static` para `<raiz-do-repositorio>/app/static`. Se não houver mapeamento, o Flask serve esses arquivos.
3. Confira que o virtualenv do web app contém `Flask` e `requests`, e que o diretório de trabalho/repositório usado pelo endpoint `/internal/deploy` é o clone correto.

O import antigo `from app import app as application` também é aceito pelo pacote atual, desde que a raiz do repositório esteja no `sys.path`. Se o site estiver retornando 500 antes do deploy automático, atualize o clone manualmente no console do PythonAnywhere (`git pull --ff-only origin main` na raiz do repositório), ajuste o WSGI conforme acima e recarregue o web app. A rota `/internal/deploy` só volta a funcionar depois que o WSGI carregar a aplicação.

Se o log mostrar `column grupos.publico does not exist`, execute no SQL Editor do Supabase a migração [`20261116140000_grupos_visibilidade_publica.sql`](../app/supabase/migrations/20261116140000_grupos_visibilidade_publica.sql). Confira também as migrações subsequentes de propriedade dos placares e CORS, na ordem cronológica, antes de usar essas funcionalidades.

Depois, publique a alteração no branch `main`. O workflow [`deploy-pythonanywhere.yml`](../.github/workflows/deploy-pythonanywhere.yml) chama `/internal/deploy`, que atualiza o clone e as dependências, recarrega o web app pela API do PythonAnywhere. Confira as páginas após o reload; a verificação automatizada adicional depende de permissão `workflow` no GitHub. O endpoint exige `DEPLOY_TOKEN` e o workflow exige os secrets `PA_DEPLOY_TOKEN` e `PA_API_TOKEN` no ambiente GitHub `PythonAnywhere`.

Confira `https://rvarjao.pythonanywhere.com/healthz` (resposta com `"estrutura":"app"`), `/`, `/admin/login`, `/exemplos/campeonato/`, `/exemplos/placar-eletronico/` e `/static/styles.css`. A API de placares exige token de grupo, então um GET sem token deve retornar 401.

Os caminhos públicos permanecem iguais. A mudança afeta a localização do código, templates e arquivos estáticos no servidor.
