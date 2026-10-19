# Projeto interdisciplinar — Campeonato e Placar Eletrônico

## Objetivo

Desenvolver dois sistemas independentes que se comunicam por uma API REST em HTTP/JSON. O projeto-base traz apenas arquivos, importações, caminhos de rotas e TODOs; **não há implementação de regras de negócio**.

## Arquitetura

- Cada grupo mantém seu próprio código no GitHub.
- Um computador na rede da escola executa a API Flask com Docker (ex.: IP reservado `192.168.1.100`, porta 5001).
- PostgreSQL fica no Supabase; idealmente, cada grupo possui projeto e credenciais separados.
- Apenas o backend da API acessa o banco do placar; o grupo de campeonatos não acessa suas tabelas.
- O servidor precisa de internet para acessar o Supabase, e a rede local precisa permitir conexões entre computadores.
- Nunca inserir credenciais no GitHub nem no código JavaScript do navegador.

## Responsabilidades

**Campeonatos:** cadastra partidas; chama POST para criar placar; salva `placar_id` no próprio banco; chama GET periodicamente (sugestão: a cada 5 segundos), exibe resultado e interrompe consultas ao finalizar.

**Placar eletrônico:** expõe POST/GET/PATCH; persiste dados; controla status, pontuação, etapas, cronômetro e faltas; fornece interface do operador e visualização pública.

## Modalidades

- Futebol/futsal: gols, tempos de jogo e cronômetro crescente; faltas se aplicável.
- Basquete: pontos, quartos, cronômetro regressivo e faltas.
- Vôlei: pontos do set atual e sets vencidos; tempo opcional.

Criar uma interface genérica primeiro; depois especializar por modalidade **sem duplicar toda a aplicação**. `modalidade` e `status` são textos com valores válidos fixos na aplicação; `etapa` é texto livre. `detalhes` contém dados específicos (sets vencidos etc.).

## Etapas propostas

1. Fazer fork e definir responsabilidades.
2. Ler e validar o contrato JSON conjunto.
3. Implementar banco, POST e GET.
4. Implementar PATCH, validação e autorização.
5. Criar visualização e controles do placar genérico.
6. Integrar Campeonatos usando polling.
7. Especializar interfaces para diferentes esportes.
8. Demonstrar partida completa e falhas controladas.

## Critérios de aceitação

- POST retorna 201 e ID persistente; GET retorna resultado atual ou 404.
- PATCH altera só campos autorizados, com tratamento de erros.
- Gerenciamento guarda o ID e não acessa o banco do placar.
- Interface usa dados coerentes com o esporte.
- Ambas as aplicações funcionam separadamente pela rede local.
- Há testes, documentação e tratamento de falhas de rede.
