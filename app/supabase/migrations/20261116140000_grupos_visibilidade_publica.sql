-- Executar no SQL Editor do Supabase antes do deploy desta versão.
-- Grupos existentes preservam a visibilidade; novos grupos são privados por padrão.
BEGIN;
ALTER TABLE public.grupos ADD COLUMN IF NOT EXISTS publico smallint;
UPDATE public.grupos SET publico = 1 WHERE publico IS NULL;
ALTER TABLE public.grupos ALTER COLUMN publico SET DEFAULT 0;
ALTER TABLE public.grupos ALTER COLUMN publico SET NOT NULL;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'grupos_publico_check' AND conrelid = 'public.grupos'::regclass) THEN
    ALTER TABLE public.grupos ADD CONSTRAINT grupos_publico_check CHECK (publico IN (0, 1));
  END IF;
END $$;
COMMIT;
-- Para ocultar o grupo pessoal, use a edição administrativa ou, antes do deploy,
-- identifique o ID correto com SELECT id, nome, ativo, publico FROM public.grupos;
-- UPDATE public.grupos SET publico = 0 WHERE id = <ID_DO_GRUPO>;
