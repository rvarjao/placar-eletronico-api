-- Grupos do Interclasse 2026, exibidos na página inicial (ordem = id).
-- Fontes: respostas do formulário de inscrição (19/10 a 28/10/2026), cards que
-- estavam fixos em templates/index.html e o projeto Interclasse Interativo.
-- URL: página publicada quando existe; senão, o repositório GitHub.
-- E-mail, documento e apresentação do formulário não possuem coluna no sistema.
-- Tokens de API não são criados aqui: gere-os pelo painel (Grupos e tokens → Gerar novo token).
-- Idempotente: grupos já existentes (mesmo nome) são ignorados.
do $$
declare
  r record;
  v_grupo_id bigint;
begin
  for r in
    select * from (values
      ('Associação U.C',
       'Organização e acompanhamento do vôlei de praia.',
       'https://rodriguesdesahellen44-cmd.github.io/placar.volei/',
       timestamptz '2026-10-19 10:41:39-03',
       array['Maria Alencar', 'Amanda Miquelin', 'Hellen de Sá']),
      ('Placar de vôlei de praia',
       'Placar digital e gestão de partidas.',
       null,
       null,
       array[]::text[]),
      ('Chaveamento',
       'Organização de confrontos para o torneio de vôlei de praia.',
       'https://github.com/vfrancini/chaveamento-de-volei',
       timestamptz '2026-10-19 11:29:51-03',
       array['Raul', 'Francini', 'Giovana']),
      ('Arena',
       'Campeonato, placares e classificação.',
       'https://valada0.github.io/arena-/',
       null,
       array[]::text[]),
      ('Interclasse Interativo',
       'Portal de notícias sobre o evento Interclasse.',
       'https://biapedrozo.github.io/interclasse-interativo',
       null,
       array['Beatriz Pedrozo']),
      ('Mesa pro',
       'Gerenciador de Interclasse de vôlei de mesa.',
       'https://github.com/KellEze/MEsa-pro',
       timestamptz '2026-10-28 22:09:25-03',
       array['Kelvyn Juan Bandeira de Freitas', 'Nicolas Modos Thomaz da Silva', 'Raul Henrique de Souza da Silva'])
    ) as t(nome, descricao, url, criado_em, integrantes)
  loop
    continue when exists (select 1 from public.grupos g where lower(g.nome) = lower(r.nome));
    insert into public.grupos (nome, descricao, url, criado_em)
    values (r.nome, r.descricao, r.url, coalesce(r.criado_em, now()))
    returning id into v_grupo_id;
    perform public.definir_integrantes_grupo(v_grupo_id, r.integrantes);
  end loop;
end $$;
