import asyncio
from typing import Annotated, Any, Dict

from fastmcp import Context
from pydantic import Field

from clients.odoo_client import OdooClientError, OdooSessionClient


def _get_client(ctx: Context) -> OdooSessionClient:
    client = (ctx.lifespan_context or {}).get("odoo")
    if not isinstance(client, OdooSessionClient):
        raise RuntimeError(
            "Odoo client not found in lifespan context. "
            "Is the MCP server running correctly?"
        )
    return client


async def create_partner(
    name: Annotated[str, Field(description="Partner display name, e.g. 'ACME SARL'.")],
    partner_type: Annotated[
        str,
        Field(
            description=(
                "Partner business role: 'customer', 'vendor', or 'both'. "
                "Defaults to 'customer'."
            )
        ),
    ] = "customer",
    is_company: Annotated[
        bool,
        Field(description="Whether this partner is a company (true) or an individual (false)."),
    ] = True,
    email: Annotated[str | None, Field(description="Optional email address.")] = None,
    phone: Annotated[str | None, Field(description="Optional phone number.")] = None,
    vat: Annotated[str | None, Field(description="Optional tax/VAT number.")] = None,
    street: Annotated[str | None, Field(description="Optional street address.")] = None,
    city: Annotated[str | None, Field(description="Optional city.")] = None,
    ctx: Context = None,
) -> Dict[str, Any]:
    """Create a new Odoo partner (customer or vendor)."""

    if not isinstance(name, str) or not name.strip():
        return {"ok": False, "error": "name is required and must be a non-empty string."}

    normalized_role = (partner_type or "customer").strip().lower()
    if normalized_role not in {"customer", "vendor", "both"}:
        return {
            "ok": False,
            "error": "partner_type must be one of: customer, vendor, both.",
        }

    try:
        client = _get_client(ctx)
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}

    try:
        await ctx.info(f"Creating partner: {name.strip()}")

        vals: Dict[str, Any] = {
            "name": name.strip(),
            "is_company": bool(is_company),
            "company_type": "company" if bool(is_company) else "person",
        }

        if normalized_role in {"customer", "both"}:
            vals["customer_rank"] = 1
        if normalized_role in {"vendor", "both"}:
            vals["supplier_rank"] = 1

        optional_fields = {
            "email": email,
            "phone": phone,
            "vat": vat,
            "street": street,
            "city": city,
        }
        for field_name, value in optional_fields.items():
            if value and str(value).strip() and str(value).strip().lower() != "null":
                vals[field_name] = str(value).strip()

        partner_id = await asyncio.to_thread(client.create_partner, vals=vals)
        partner = await asyncio.to_thread(client.read_partner, record_id=partner_id)
        await ctx.info(f"Partner created: id={partner_id} name={partner.get('name')}")

        return {
            "ok": True,
            "message": f"Partner created successfully: {partner.get('name')}",
            "partner": partner,
            "summary": {
                "id": partner.get("id"),
                "name": partner.get("name"),
                "email": partner.get("email"),
                "phone": partner.get("phone"),
                "customer_rank": partner.get("customer_rank"),
                "supplier_rank": partner.get("supplier_rank"),
            },
        }
    except OdooClientError as exc:
        await ctx.warning(f"Odoo error: {exc}")
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        await ctx.warning(f"Unexpected error: {exc}")
        return {"ok": False, "error": f"Unexpected error: {exc}"}
