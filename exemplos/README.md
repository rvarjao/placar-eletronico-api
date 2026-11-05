# Exemplos

- [api-completa](api-completa/README.md): API publicada, painel administrativo, grupos, tokens e monitoramento.
- [placar-eletronico](placar-eletronico/README.md): placar local didático, porta 5001, operador e telão.
- [campeonato](campeonato/README.md): gerenciador que pode usar a API publicada com token de grupo ou o placar local.

## Testar um token de grupo

Configure no exemplo de campeonato:

```bash
export PLACAR_URL="https://rvarjao.pythonanywhere.com"
export PLACAR_TOKEN="COLE_AQUI_O_TOKEN_DO_GRUPO"
python exemplos/campeonato/app.py
```

O token é enviado pelo backend no cabeçalho `Authorization: Bearer`. Nunca coloque o token no JavaScript do navegador ou em um commit.
