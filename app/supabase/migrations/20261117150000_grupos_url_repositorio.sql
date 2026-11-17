alter table public.grupos add column if not exists url_repositorio text
  check (url_repositorio is null or url_repositorio ~* '^https?://');

-- Aproveita links de repositório do GitHub já cadastrados como URL do projeto.
update public.grupos
set url_repositorio = url
where url_repositorio is null
  and url ~* '^https?://(www\.)?github\.com/[^/?#]+/[^/?#]+/?$';

notify pgrst, 'reload schema';
