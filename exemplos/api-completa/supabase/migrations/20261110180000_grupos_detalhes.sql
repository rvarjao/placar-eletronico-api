-- Detalhes do projeto de cada grupo: descrição, URL e integrantes.
alter table public.grupos add column if not exists descricao text;
alter table public.grupos add column if not exists url text
  check (url is null or url ~* '^https?://');
alter table public.grupos add column if not exists integrantes text[] not null default '{}';
