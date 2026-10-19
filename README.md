# API de Placar Eletrônico — projeto-base

Projeto didático: gerenciamento de campeonatos consulta uma API de placar em Flask, usando Docker na escola e PostgreSQL no Supabase.

**Os endpoints estão intencionalmente sem implementação (HTTP 501).**

## Documentação
- [Guia da atividade](docs/guia-da-atividade.md)
- [Contrato JSON e rotas](docs/contrato-api.md)
- [Integração entre grupos](docs/integracao.md)

## Começar
1. Faça fork e trabalhe em branches.
2. Copie `.env.example` para `.env` e configure o banco, sem publicar segredos.
3. Inicie com `docker compose up --build`.
4. Implemente POST/GET/PATCH seguindo o contrato; teste com curl/Postman.

A API local ficará na porta `5001`. O Supabase requer conexão com a internet.
