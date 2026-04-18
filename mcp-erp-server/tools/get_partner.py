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


async def get_partner(
    partner_id: Annotated[int | None, Field(description="Odoo partner ID.")] = None,
    partner_name: Annotated[
        str | None,
        Field(description="Partner name to search case-insensitively (first match)."),
    ] = None,
    ctx: Context = None,
) -> Dict[str, Any]:
    """Get an Odoo partner by ID or by name (case-insensitive)."""

    has_id = partner_id is not None
    has_name = bool(partner_name and str(partner_name).strip())

    if not has_id and not has_name:
        return {
            "ok": False,
            "error": "Provide either partner_id or partner_name.",
        }

    try:
        client = _get_client(ctx)
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}

    try:
        if has_id:
            await ctx.info(f"Reading partner id={partner_id}")
            partner = client.read_partner(record_id=partner_id)
        else:
            name = str(partner_name).strip()
            await ctx.info(f"Searching partner by name: {name}")
            matches = client.search_partners(
                filters={"domain": [["name", "ilike", name]]},
                limit=1,
            )
            if not matches:
                return {
                    "ok": False,
                    "error": f"No partner found with name '{name}'.",
                }
            partner = matches[0]

        await ctx.info(f"Partner fetched — id {partner.get('id')}")

        return {
            "ok": True,
            "message": "Partner data fetched successfully",
            "summary": {
                "id": partner.get("id"),
                "name": partner.get("name"),
                "email": partner.get("email"),
                "phone": partner.get("phone"),
                "is_company": partner.get("is_company"),
                "customer_rank": partner.get("customer_rank"),
                "supplier_rank": partner.get("supplier_rank"),
            },
            "partner": partner,
            "data": partner,
        }
    except OdooClientError as exc:
        await ctx.warning(f"Odoo error: {exc}")
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        await ctx.warning(f"Unexpected error: {exc}")
        return {"ok": False, "error": f"Unexpected error: {exc}"}
