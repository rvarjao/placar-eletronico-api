-- Aplicar no Supabase ANTES de publicar o código que depende desta coluna.
BEGIN;
ALTER TABLE public.placares ADD COLUMN IF NOT EXISTS grupo_id bigint;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname = 'placares_grupo_id_fkey'
                   AND conrelid = 'public.placares'::regclass) THEN
    ALTER TABLE public.placares ADD CONSTRAINT placares_grupo_id_fkey
      FOREIGN KEY (grupo_id) REFERENCES public.grupos(id) ON DELETE RESTRICT;
  END IF;
END $$;
CREATE INDEX IF NOT EXISTS placares_grupo_id_idx ON public.placares(grupo_id);

-- Recuperar somente proprietários comprovados por criação bem-sucedida.
-- Havendo registros de criação conflitantes, não atribuir automaticamente.
WITH criadores AS (
  SELECT placar_id, min(grupo_id) AS grupo_id
  FROM public.requisicoes_api
  WHERE metodo = 'POST' AND status = 201 AND placar_id IS NOT NULL
    AND grupo_id IS NOT NULL
    AND rota = '/api/placares/criar'
  GROUP BY placar_id
  HAVING count(DISTINCT grupo_id) = 1
)
UPDATE public.placares p
SET grupo_id = c.grupo_id
FROM criadores c
JOIN public.grupos g ON g.id = c.grupo_id
WHERE p.id = c.placar_id AND p.grupo_id IS NULL;

COMMIT;
NOTIFY pgrst, 'reload schema';

-- Conferência: atribuir manualmente somente após confirmar a propriedade.
SELECT id, nome_equipe_a, nome_equipe_b, grupo_id
FROM public.placares WHERE grupo_id IS NULL ORDER BY id;
