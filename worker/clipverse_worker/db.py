"""Talks to the Supabase database over its REST API, using the SECRET key.

The secret key bypasses privacy rules, so this code must only run on our own
machine/server - never in a browser.

`Db` is deliberately tiny (select / insert / update / rpc) so tests can swap in
an in-memory fake (see tests/fakes.py).
"""
from __future__ import annotations

from typing import Any

import httpx


class DbError(Exception):
    pass


class Db:
    def __init__(self, supabase_url: str, secret_key: str, timeout: float = 30.0):
        self._http = httpx.Client(
            base_url=f"{supabase_url}/rest/v1",
            headers={
                "apikey": secret_key,
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            timeout=timeout,
        )

    def _check(self, res: httpx.Response) -> Any:
        if res.status_code >= 400:
            raise DbError(f"Database error {res.status_code}: {res.text[:300]}")
        return res.json() if res.content else None

    @staticmethod
    def _filters(where: dict[str, Any]) -> dict[str, str]:
        return {k: f"eq.{v}" for k, v in where.items()}

    def select(self, table: str, where: dict[str, Any], columns: str = "*",
               order: str | None = None) -> list[dict]:
        params = self._filters(where) | {"select": columns}
        if order:
            params["order"] = order
        return self._check(self._http.get(f"/{table}", params=params))

    def select_one(self, table: str, where: dict[str, Any]) -> dict | None:
        rows = self.select(table, where)
        return rows[0] if rows else None

    def insert(self, table: str, rows: list[dict] | dict) -> list[dict]:
        return self._check(self._http.post(f"/{table}", json=rows))

    def update(self, table: str, where: dict[str, Any], values: dict) -> list[dict]:
        return self._check(self._http.patch(f"/{table}", params=self._filters(where), json=values))

    def delete(self, table: str, where: dict[str, Any]) -> None:
        self._check(self._http.delete(f"/{table}", params=self._filters(where)))

    def rpc(self, fn: str, args: dict | None = None) -> Any:
        return self._check(self._http.post(f"/rpc/{fn}", json=args or {}))
