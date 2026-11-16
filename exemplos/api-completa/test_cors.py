"""Testes de CORS e origem sem acessar o banco de produção."""
import os
import unittest
from unittest.mock import Mock, patch

os.environ["EXEMPLO_POLLING"] = "0"
import app as modulo
import cors_api


class CorsTest(unittest.TestCase):
    def setUp(self):
        self.client = modulo.app.test_client()
        self.banco = Mock()
        self.banco.all.return_value = []
        self.origem = "https://aluno.github.io"
        self.outra = "https://outro.github.io"
        self.grupo = {"id": 1, "nome": "A", "origem_permitida": self.origem,
                      "restringir_origem": 1}
        self.banco.one.side_effect = lambda tabela, **kw: (
            {"id": 1} if kw.get("filters", {}).get("origem_permitida")
            in ("eq." + self.origem, "eq." + self.outra) else None
        )
        for p in (
            patch.object(modulo, "db", return_value=self.banco),
            patch.object(cors_api, "db", return_value=self.banco),
            patch.object(modulo, "autenticar_token", side_effect=lambda t: self.grupo if t == "teste" else None),
            patch.object(modulo, "registrar_requisicao"),
        ):
            p.start()
            self.addCleanup(p.stop)

    def headers(self, origem=None, token="teste"):
        h = {"Authorization": "Bearer " + token}
        if origem is not None:
            h["Origin"] = origem
        return h

    def preflight(self, origem, metodo="PATCH", cabecalhos="authorization,content-type"):
        return self.client.options("/api/placares/10", headers={
            "Origin": origem, "Access-Control-Request-Method": metodo,
            "Access-Control-Request-Headers": cabecalhos,
        })

    def test_preflight_sem_token(self):
        r = self.preflight(self.origem)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r.headers["Access-Control-Allow-Origin"], self.origem)
        self.assertIn("Authorization", r.headers["Access-Control-Allow-Headers"])
        self.assertIn("Origin", r.headers["Vary"])
        modulo.registrar_requisicao.assert_not_called()

    def test_preflight_origem_desconhecida(self):
        r = self.preflight("https://desconhecido.github.io")
        self.assertEqual(r.status_code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", r.headers)

    def test_preflight_metodo_e_header_nao_permitidos(self):
        self.assertEqual(self.preflight(self.origem, "TRACE").status_code, 403)
        self.assertEqual(self.preflight(self.origem, cabecalhos="x-invalido").status_code, 403)

    def test_origem_do_grupo_permitida(self):
        r = self.client.get("/api/placares", headers=self.headers(self.origem))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Access-Control-Allow-Origin"], self.origem)

    def test_origem_de_outro_grupo_bloqueada(self):
        r = self.client.get("/api/placares", headers=self.headers(self.outra))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.headers["Access-Control-Allow-Origin"], self.outra)
        self.banco.all.assert_not_called()

    def test_sem_origem_restrito(self):
        self.assertEqual(self.client.get("/api/placares", headers=self.headers()).status_code, 403)

    def test_sem_origem_servidor(self):
        self.grupo["restringir_origem"] = 0
        r = self.client.get("/api/placares", headers=self.headers())
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Access-Control-Allow-Origin", r.headers)

    def test_sem_restricao_nao_libera_origem_aleatoria(self):
        self.grupo["restringir_origem"] = 0
        r = self.client.get("/api/placares", headers=self.headers("https://desconhecido.github.io"))
        self.assertEqual(r.status_code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", r.headers)

    def test_token_invalido_na_origem_cadastrada(self):
        r = self.client.get("/api/placares", headers=self.headers(self.origem, "invalido"))
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.headers["Access-Control-Allow-Origin"], self.origem)

    def test_origens_invalidas(self):
        for origem in ("null", "*", "https://aluno.github.io/projeto", "https://user@aluno.github.io"):
            with self.subTest(origem=origem):
                with self.assertRaises(ValueError):
                    cors_api.normalizar_origem(origem)

    def test_normalizacao(self):
        self.assertEqual(cors_api.normalizar_origem("https://ALUNO.github.io:443/"), self.origem)
        self.assertEqual(cors_api.normalizar_origem("http://localhost:5500"), "http://localhost:5500")


if __name__ == "__main__":
    unittest.main()
