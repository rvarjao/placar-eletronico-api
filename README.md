# API de Placar Eletrônico — projeto-base

Projeto didático de integração entre **Gerenciamento de Campeonatos** (cliente) e **Placar Eletrônico** (API Flask). A execução será por Docker na rede local da escola, com persistência no PostgreSQL do Supabase.

**As três rotas estão declaradas, mas sem implementação (respondem HTTP 501).** O objetivo é que os alunos programem o comportamento.

## Documentação
- [Guia da atividade](docs/guia-da-atividade.md)
- [Contrato da API e exemplos JSON](docs/contrato-api.md)
- [Integração via polling](docs/integracao.md)
- [Exemplos de referência](exemplos/README.md): API completa, Placar Eletrônico (5001) e Gerenciador de Campeonato (5002)

## Estrutura
- `app/routes/placares.py`: POST, GET e PATCH definidos, com TODOs.
- `app/services/`: regras de negócio a implementar.
- `app/repositories/`: acesso ao banco a implementar.
- `app/models/`: modelagem a implementar.
- `Dockerfile` e `compose.yaml`: execução local.
- `.env.example`: exemplo sem credenciais.
- `tests/`: testes a desenvolver.

## Início
1. Faça um fork e trabalhe em branches.
2. Copie `.env.example` para `.env` com credenciais válidas do Supabase; não publique segredos.
3. Execute `docker compose up --build` e abra a porta 5001 da máquina da escola.
4. Implemente as rotas conforme o contrato e teste com curl ou Postman.

O servidor requer internet para o Supabase. O acesso entre computadores depende das configurações da rede local.
