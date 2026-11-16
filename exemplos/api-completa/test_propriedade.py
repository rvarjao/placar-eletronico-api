"""Testes da API de propriedade, sem conexão com o Supabase.
Executar em exemplos/api-completa: python -m unittest test_propriedade.py
"""
import os
import unittest
from unittest.mock import patch, Mock

os.environ["EXEMPLO_POLLING"] = "0"
import app as modulo


class PropriedadeTest(unittest.TestCase):
    def setUp(self):
        self.client = modulo.app.test_client()
        self.banco = Mock()
        self.banco.one.return_value = {"id": 10, "grupo_id": 1}
        self.banco.update.return_value = [{"id": 10, "grupo_id": 1}]
        self.banco.delete.return_value = [{"id": 10, "grupo_id": 1}]
        self.banco.insert.return_value = {"id": 10, "grupo_id": 1}
        self.grupo = {"id": 1, "nome": "Grupo A"}
        self.headers = {"Authorization": "Bearer teste"}
        for p in (patch.object(modulo, "db", return_value=self.banco),
                  patch.object(modulo, "autenticar_token", side_effect=lambda t: self.grupo if t else None),
                  patch.object(modulo, "registrar_requisicao")):
            p.start()
            self.addCleanup(p.stop)

    def test_criacao_ignora_proprietario_enviado(self):
        r = self.client.post("/api/placares/criar", headers=self.headers,
            json={"nome_equipe_a": "A", "nome_equipe_b": "B", "modalidade": "volei", "grupo_id": 2})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.banco.insert.call_args.args[1]["grupo_id"], 1)

    def test_patch_proprio(self):
        r = self.client.patch("/api/placares/10", headers=self.headers, json={"pontos_a": 2})
        self.assertEqual(r.status_code, 200)
        self.banco.update.assert_called_once_with("placares", {"pontos_a": 2}, {"id": "eq.10", "grupo_id": "eq.1"})

    def test_escritas_alheias_bloqueadas(self):
        self.banco.one.return_value = {"id": 10, "grupo_id": 2}
        for method in ("patch", "put", "delete"):
            with self.subTest(method=method):
                r = getattr(self.client, method)("/api/placares/10", headers=self.headers, json={})
                self.assertEqual(r.status_code, 403)
        self.banco.update.assert_not_called()
        self.banco.delete.assert_not_called()

    def test_sem_proprietario_bloqueado(self):
        self.banco.one.return_value = {"id": 10, "grupo_id": None}
        r = self.client.patch("/api/placares/10", headers=self.headers, json={"pontos_a": 2})
        self.assertEqual(r.status_code, 403)
        self.banco.update.assert_not_called()

    def test_leitura_compartilhada(self):
        self.banco.one.return_value = {"id": 10, "grupo_id": 2}
        self.assertEqual(self.client.get("/api/placares/10", headers=self.headers).status_code, 200)

    def test_placar_inexistente(self):
        self.banco.one.return_value = None
        self.assertEqual(self.client.delete("/api/placares/10", headers=self.headers).status_code, 404)

    def test_exclusao_propria(self):
        self.assertEqual(self.client.delete("/api/placares/10", headers=self.headers).status_code, 204)
        self.banco.delete.assert_called_once_with("placares", {"id": "eq.10", "grupo_id": "eq.1"})


if __name__ == "__main__":
    unittest.main()
