-- Aplicar antes do deploy. Grupos existentes mantêm chamadas servidor a servidor.
BEGIN;
ALTER TABLE public.grupos ADD COLUMN IF NOT EXISTS origem_permitida text;
ALTER TABLE public.grupos ADD COLUMN IF NOT EXISTS restringir_origem smallint NOT NULL DEFAULT 0;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'grupos_restringir_origem_check' AND conrelid = 'public.grupos'::regclass) THEN
    ALTER TABLE public.grupos ADD CONSTRAINT grupos_restringir_origem_check
      CHECK (restringir_origem IN (0,1) AND (restringir_origem = 0 OR (origem_permitida IS NOT NULL AND btrim(origem_permitida) <> '')));
  END IF;
END $$;
CREATE INDEX IF NOT EXISTS grupos_origem_permitida_idx ON public.grupos(origem_permitida) WHERE ativo = 1;
COMMIT;
NOTIFY pgrst, 'reload schema';
