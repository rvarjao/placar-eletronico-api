"""Acesso administrativo ao PostgREST Supabase, somente no servidor Flask."""
import os
import requests


class SupabaseError(RuntimeError):
    pass


class SupabaseDB:
    def __init__(self):
        url = os.getenv("SUPABASE_URL", "").rstrip("/")
        key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError("Configure SUPABASE_URL e SUPABASE_SECRET_KEY no servidor")
        if not url.startswith("https://"):
            raise RuntimeError("SUPABASE_URL deve usar HTTPS")
        self.base_url = url
        self.url = url + "/rest/v1"
        self.headers = {"apikey": key, "Accept": "application/json"}
        if not key.startswith("sb_secret_"):
            self.headers["Authorization"] = "Bearer " + key
        # Para o Auth basta a chave publicável; se ausente, usa a chave do servidor.
        self.auth_key = os.getenv("SUPABASE_PUBLISHABLE_KEY") or key
        self.session = requests.Session()

    def autenticar_usuario(self, email, senha):
        """Valida e-mail e senha de um usuário do Supabase Auth.

        Retorna o objeto ``user`` em caso de sucesso, ``None`` para credenciais
        inválidas e levanta ``SupabaseError`` para falhas de comunicação.
        """
        headers = {"apikey": self.auth_key, "Content-Type": "application/json"}
        try:
            response = self.session.post(
                self.base_url + "/auth/v1/token",
                params={"grant_type": "password"},
                json={"email": email, "password": senha},
                headers=headers, timeout=12,
            )
        except requests.RequestException as error:
            raise SupabaseError(f"Falha no Supabase Auth: {error}") from error
        if response.status_code in (400, 401, 403, 422):
            return None
        if not response.ok:
            raise SupabaseError(f"Falha no Supabase Auth: HTTP {response.status_code}")
        return response.json().get("user")

    def request(self, method, resource, params=None, data=None, prefer=None):
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer
        try:
            response = self.session.request(
                method, self.url + "/" + resource,
                params=params, json=data, headers=headers, timeout=12,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            raise SupabaseError(f"Falha no Supabase ao acessar {resource}: {error}") from error
        return response.json() if response.content else None

    def select(self, table, *, columns="*", filters=None, order=None, limit=None):
        params = {"select": columns, **(filters or {})}
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = limit
        return self.request("GET", table, params=params) or []

    def one(self, table, *, columns="*", filters=None):
        rows = self.select(table, columns=columns, filters=filters, limit=1)
        return rows[0] if rows else None

    def insert(self, table, data):
        rows = self.request("POST", table, data=data, prefer="return=representation")
        return rows[0] if isinstance(data, dict) else rows

    def update(self, table, data, filters):
        return self.request("PATCH", table, params=filters, data=data, prefer="return=representation") or []

    def delete(self, table, filters):
        return self.request("DELETE", table, params=filters, prefer="return=representation") or []

    def all(self, table, *, columns="*", filters=None, order=None, batch=1000):
        """Paginação para que dashboards não percam dados após mil linhas."""
        out = []
        start = 0
        while True:
            params = {"select": columns, **(filters or {}), "limit": batch, "offset": start}
            if order:
                params["order"] = order
            rows = self.request("GET", table, params=params) or []
            out.extend(rows)
            if len(rows) < batch:
                return out
            start += batch

    def state_get(self, chave, default=None):
        row = self.one("estado_aplicacoes", columns="dados", filters={"chave": f"eq.{chave}"})
        return row["dados"] if row is not None else default

    def state_set(self, chave, dados):
        # UPSERT cria ou substitui o estado; nenhum arquivo local é gravado.
        return self.request("POST", "estado_aplicacoes",
                            params={"on_conflict": "chave"},
                            data={"chave": chave, "dados": dados},
                            prefer="resolution=merge-duplicates,return=minimal")

    def rpc(self, name, params=None):
        return self.request("POST", "rpc/" + name, data=params or {})


_db = None


def db():
    global _db
    if _db is None:
        _db = SupabaseDB()
    return _db
