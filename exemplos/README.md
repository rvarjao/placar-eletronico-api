# Exemplos

- [api-completa](api-completa/README.md): API publicada, painel administrativo, grupos, tokens e monitoramento.
- [placar-eletronico](placar-eletronico/README.md): telas de operador e de telão que usam a API publicada com o token de um grupo.
- [campeonato](campeonato/README.md): gerenciador que cria e acompanha placares pela API publicada com o token de um grupo (ou pelo placar local).

Os dois sistemas são independentes: cada um tem a própria tela de configuração e guarda o próprio token.

## Configurar o token pela tela

No servidor publicado, os dois sistemas ficam em `/exemplos/campeonato/` e `/exemplos/placar-eletronico/`.

1. Entre na área administrativa e gere o token em **Grupos e tokens** (ele aparece uma única vez).
2. Abra **Configurar Campeonato** ou **Configurar Placar Eletrônico** no menu do painel (`/exemplos/<sistema>/configuracao`).
3. Cole o token e clique em **Salvar e testar**. Em branco, o endereço da API é o próprio servidor.

Só o administrador logado abre essas telas. O token fica em `conexao_api.json` dentro da pasta de cada sistema (ignorado pelo git) e é enviado pelo backend no cabeçalho `Authorization: Bearer`. Ele nunca é mostrado de novo na tela, nem vai para o JavaScript do navegador. Para trocar, cole outro token; para limpar, use **Remover token**.

## Rodar um sistema na sua máquina

Fora do servidor principal a tela `/configuracao` abre sem login (uso local). Informe o endereço da API (por exemplo `https://rvarjao.pythonanywhere.com`) e o token do grupo. Também é possível usar variáveis de ambiente como valores iniciais:

```bash
export PLACAR_URL="https://rvarjao.pythonanywhere.com"
export PLACAR_TOKEN="COLE_AQUI_O_TOKEN_DO_GRUPO"
python exemplos/campeonato/app.py
```

O que for salvo na tela tem prioridade sobre as variáveis. Nunca coloque o token no JavaScript do navegador ou em um commit.
