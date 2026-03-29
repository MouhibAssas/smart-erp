import json
import os
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from clients.base_client import BaseERPClient


class OdooClientError(Exception):
    """Raised for any Odoo API error — auth failures, ORM errors, HTTP errors."""
    pass


class OdooSessionClient(BaseERPClient):
    """
    Odoo 19 client using the JSON-2 API.

    Verified from Odoo 19 official docs:
      POST /json/2/<model>/<method>
      Headers:
        Authorization: bearer <api_key>
        X-Odoo-Database: <db>
        Content-Type: application/json

    Stateless — no session, no cookies, no uid.
    One client instance is created at MCP server startup via lifespan
    and shared across all tool calls via ctx.lifespan_context["odoo"].

    How to get your API key:
      Odoo → Preferences → Account Security → New API Key
    """

    INVOICE_READ_FIELDS = [
        "id", "name", "move_type", "state",
        "invoice_date", "invoice_date_due",
        "ref", "amount_total", "partner_id",
    ]

    def __init__(
        self,
        base_url: Optional[str] = None,
        db: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("ODOO_URL") or "http://localhost:8069"
        ).rstrip("/")
        self.db = db or os.getenv("ODOO_DB")
        self.api_key = api_key or os.getenv("ODOO_API_KEY")
        self.timeout = timeout

        if not self.db:
            raise OdooClientError("Missing ODOO_DB — set it in your .env file")
        if not self.api_key:
            raise OdooClientError(
                "Missing ODOO_API_KEY — generate one in Odoo: "
                "Preferences → Account Security → New API Key"
            )

    # ──────────────────────────────────────────────
    # BaseERPClient interface
    # ──────────────────────────────────────────────

    def authenticate(self) -> None:
        """
        JSON-2 is stateless — there is no login step.
        This does a lightweight ping to confirm the API key works
        and Odoo is reachable. Call once at startup in lifespan.
        """
        try:
            self._call("res.users", "context_get")
        except OdooClientError as exc:
            raise OdooClientError(
                f"Odoo connection check failed — is the API key valid? {exc}"
            ) from exc

    def create_invoice(
        self,
        vals: Dict[str, Any],
        model: str = "account.move",
    ) -> int:
        """
        Creates one invoice record via ORM create.

        vals shape (verified from Odoo 19 docs):
          move_type        : "out_invoice" | "in_invoice"
          partner_id       : int  — Odoo partner ID
          invoice_line_ids : list — ORM Command format: [0, 0, {line fields}]
          invoice_date     : "YYYY-MM-DD"  (optional)
          invoice_date_due : "YYYY-MM-DD"  (optional)
          ref              : str           (optional)
          journal_id       : int           (optional)
          currency_id      : int           (optional)

        ORM Command [0, 0, {...}] means "create a new related record inline".
        tax_ids on lines use [6, 0, [id1, id2]] = "replace with this set".

        Returns the integer ID of the created record.
        """
        result = self._call(model, "create", **vals)
        if not isinstance(result, int):
            raise OdooClientError(
                f"Expected int from create, got: {type(result).__name__} = {result}"
            )
        return result

    def read_invoice(
        self,
        record_id: Any,
        model: str = "account.move",
    ) -> Dict[str, Any]:
        """Reads one invoice record by Odoo ID."""
        rid = self._coerce_id(record_id)
        records = self._call(
            model, "read",
            ids=[rid],
            fields=self.INVOICE_READ_FIELDS,
        )
        if isinstance(records, list) and records:
            return records[0]
        raise OdooClientError(f"No invoice found with id {rid}")

    def update_invoice(
        self,
        record_id: Any,
        vals: Dict[str, Any],
        model: str = "account.move",
    ) -> bool:
        rid = self._coerce_id(record_id)
        result = self._call(model, "write", ids=[rid], **vals)
        return bool(result)

    def search_invoices(
        self,
        filters: Dict[str, Any],
        limit: int = 20,
        model: str = "account.move",
    ) -> List[Dict[str, Any]]:
        domain = self._build_domain(filters)
        records = self._call(
            model, "search_read",
            domain=domain,
            fields=self.INVOICE_READ_FIELDS,
            limit=limit,
        )
        if isinstance(records, list):
            return [r for r in records if isinstance(r, dict)]
        raise OdooClientError(
            f"Unexpected search_read result: {type(records)}"
        )

    def get_monthly_revenue(
        self,
        year: int,
        month: int,
        model: str = "account.move",
    ) -> float:
        if not 1 <= month <= 12:
            raise OdooClientError("month must be between 1 and 12")
        start = f"{year:04d}-{month:02d}-01"
        end = (
            f"{year + 1:04d}-01-01"
            if month == 12
            else f"{year:04d}-{month + 1:02d}-01"
        )
        domain = [
            ["move_type", "=", "out_invoice"],
            ["state", "=", "posted"],
            ["invoice_date", ">=", start],
            ["invoice_date", "<", end],
        ]
        records = self._call(
            model, "search_read",
            domain=domain,
            fields=["amount_total"],
            limit=0,
        )
        if not isinstance(records, list):
            raise OdooClientError("Unexpected revenue result type")
        return sum(
            float(r["amount_total"])
            for r in records
            if isinstance(r.get("amount_total"), (int, float))
        )

    # ──────────────────────────────────────────────
    # Core HTTP layer — single entry point to Odoo
    # ──────────────────────────────────────────────

    def _call(
        self,
        model: str,
        method: str,
        ids: Optional[List[int]] = None,
        **kwargs: Any,
    ) -> Any:
        """
        POST /json/2/<model>/<method>

        Body:
          {
            "ids": [...],      ← record-level methods only (read/write)
            "context": {},     ← optional Odoo context
            "<param>": value,  ← named method parameters
          }

        On success: Odoo returns HTTP 200 with the method's return value.
        On error:   Odoo returns 4xx/5xx with a JSON error object.
        """
        url = f"{self.base_url}/json/2/{model}/{method}"

        body: Dict[str, Any] = {}
        if ids is not None:
            body["ids"] = ids
        body.update(kwargs)

        encoded = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(url, data=encoded, method="POST")
        req.add_header("Content-Type", "application/json; charset=utf-8")
        req.add_header("Accept", "application/json")
        req.add_header("Authorization", f"bearer {self.api_key}")
        req.add_header("X-Odoo-Database", self.db)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))

        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            try:
                msg = json.loads(raw).get("error", {}).get("message") or raw
            except Exception:
                msg = raw
            raise OdooClientError(f"Odoo HTTP {exc.code}: {msg}") from exc

        except urllib.error.URLError as exc:
            raise OdooClientError(
                f"Cannot reach Odoo at {self.base_url}: {exc.reason}"
            ) from exc

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    def _coerce_id(self, record_id: Any) -> int:
        if isinstance(record_id, bool):
            raise OdooClientError("record_id must be an integer, not bool")
        try:
            value = int(record_id)
        except (TypeError, ValueError) as exc:
            raise OdooClientError(
                f"record_id must be an integer: {record_id}"
            ) from exc
        if value <= 0:
            raise OdooClientError("record_id must be > 0")
        return value

    def _build_domain(self, filters: Dict[str, Any]) -> List[Any]:
        domain = filters.get("domain")
        if isinstance(domain, list):
            return domain
        return [
            [k, "=", v]
            for k, v in filters.items()
            if k != "domain" and v is not None
        ]