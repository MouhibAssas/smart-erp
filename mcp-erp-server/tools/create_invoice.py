import json
from typing import Annotated, Any, Dict

from fastmcp import Context
from pydantic import Field

from clients.odoo_client import OdooClientError, OdooSessionClient


# ──────────────────────────────────────────────────────
# Client helper — verified pattern from FastMCP 3.x docs
# ctx.lifespan_context is the dict yielded by @lifespan
# ──────────────────────────────────────────────────────

def _get_client(ctx: Context) -> OdooSessionClient:
    client = (ctx.lifespan_context or {}).get("odoo")
    if not isinstance(client, OdooSessionClient):
        raise RuntimeError(
            "Odoo client not found in lifespan context. "
            "Is the MCP server running correctly?"
        )
    return client


# ──────────────────────────────────────────────────────
# Odoo ORM helpers
# ──────────────────────────────────────────────────────

def _build_line(line: Dict[str, Any]) -> list:
    """
    Converts a plain line dict into the Odoo ORM Command format.

    [0, 0, {fields}] means "create a new related record inline".
    tax_ids uses [6, 0, [id1, id2]] = "replace the m2m set with these IDs".

    Verified from Odoo 19 docs and community examples.
    """
    tax_ids = line.get("tax_ids", [])
    return [0, 0, {
        "name":       line["name"],
        "quantity":   line["quantity"],
        "price_unit": line["price_unit"],
        "account_id": line["account_id"],
        **({"tax_ids": [[6, 0, tax_ids]]} if tax_ids else {}),
    }]


def _build_vals(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds the final Odoo create vals dict from the parsed input.
    Only includes optional fields when the caller actually provided them,
    so Odoo falls back to its own defaults (partner payment terms, etc.).
    """
    vals: Dict[str, Any] = {
        "move_type":        raw["move_type"],
        "partner_id":       raw["partner_id"],
        "invoice_line_ids": [_build_line(l) for l in raw["invoice_line_ids"]],
    }
    for optional in ("invoice_date", "invoice_date_due", "ref",
                     "journal_id", "currency_id"):
        if raw.get(optional) is not None:
            vals[optional] = raw[optional]
    return vals


# ──────────────────────────────────────────────────────
# MCP tool
# FastMCP reads Annotated[str, Field(description=...)]
# and exposes it in the tool schema shown to the LLM.
# Verified from FastMCP 3.x docs (gofastmcp.com).
# ──────────────────────────────────────────────────────

async def create_invoice(
    invoice_payload: Annotated[str, Field(
        description=(
            "JSON string to create an Odoo invoice. "
            "Required fields:\n"
            "  move_type        : 'out_invoice' (customer) or 'in_invoice' (vendor bill)\n"
            "  partner_id       : Odoo integer ID of the customer or vendor "
            "(Contacts → open contact → check URL for the ID)\n"
            "  invoice_line_ids : list of line objects, each with:\n"
            "      name       : description of the product or service\n"
            "      quantity   : number of units\n"
            "      price_unit : unit price before tax\n"
            "      account_id : Odoo account integer ID "
            "(Accounting → Chart of Accounts → check URL)\n"
            "      tax_ids    : optional list of Odoo tax integer IDs "
            "(Accounting → Taxes → check URL)\n"
            "Optional fields:\n"
            "  invoice_date     : 'YYYY-MM-DD' — defaults to today\n"
            "  invoice_date_due : 'YYYY-MM-DD' — defaults to partner payment terms\n"
            "  ref              : internal reference e.g. PO number\n"
            "  journal_id       : Odoo journal integer ID — defaults to sales/purchase journal\n"
            "  currency_id      : Odoo currency integer ID — defaults to company currency\n"
            "Example:\n"
            '{"move_type":"out_invoice","partner_id":7,'
            '"invoice_line_ids":[{"name":"Consulting","quantity":2,'
            '"price_unit":500.0,"account_id":11}]}'
        )
    )],
    ctx: Context,
) -> Dict[str, Any]:
    """Create a customer invoice or vendor bill in Odoo."""

    # ── Step 1: parse JSON ────────────────────────────────────────────
    try:
        raw = json.loads(invoice_payload)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"Invalid JSON: {exc}"}

    if not isinstance(raw, dict):
        return {"ok": False, "error": "invoice_payload must be a JSON object"}

    # ── Step 2: validate required fields ─────────────────────────────
    missing = [f for f in ("move_type", "partner_id", "invoice_line_ids")
               if f not in raw]
    if missing:
        return {"ok": False, "error": f"Missing required fields: {missing}"}

    if raw["move_type"] not in ("out_invoice", "in_invoice"):
        return {
            "ok": False,
            "error": "move_type must be 'out_invoice' (customer) or 'in_invoice' (vendor)",
        }

    if not isinstance(raw.get("invoice_line_ids"), list) or not raw["invoice_line_ids"]:
        return {"ok": False, "error": "invoice_line_ids must be a non-empty list"}

    for i, line in enumerate(raw["invoice_line_ids"]):
        missing_line = [f for f in ("name", "quantity", "price_unit", "account_id")
                        if f not in line]
        if missing_line:
            return {
                "ok": False,
                "error": f"Line {i} missing fields: {missing_line}",
            }

    # ── Step 3: get Odoo client from lifespan ────────────────────────
    try:
        client = _get_client(ctx)
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}

    # ── Step 4: log, build vals, create in Odoo ──────────────────────
    await ctx.info(f"Creating {raw['move_type']} for partner_id={raw['partner_id']}")

    try:
        vals = _build_vals(raw)
        record_id = client.create_invoice(vals=vals)
        record = client.read_invoice(record_id=record_id)
        await ctx.info(f"Invoice created — Odoo id {record_id}, name {record.get('name')}")
        return {
            "ok": True,
            "message": f"Invoice created with Odoo id {record_id}",
            "invoice": record,
        }

    except OdooClientError as exc:
        await ctx.warning(f"Odoo error: {exc}")
        return {"ok": False, "error": str(exc)}

    except Exception as exc:
        await ctx.warning(f"Unexpected error: {exc}")
        return {"ok": False, "error": f"Unexpected error: {exc}"}