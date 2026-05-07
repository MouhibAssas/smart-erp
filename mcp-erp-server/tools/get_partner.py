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


async def get_partner(
    partner_id: Annotated[int | None, Field(description="Odoo partner ID.")] = None,
    partner_name: Annotated[
        str | None,
        Field(description="Partner name to search case-insensitively (first match)."),
    ] = None,
    max_results: Annotated[
        int,
        Field(description="Maximum number of partner matches to return when searching by name."),
    ] = 10,
    ctx: Context = None,
) -> Dict[str, Any]:
    """Get an Odoo partner by ID or by name (case-insensitive)."""

    def _format_partner_line(partner: Dict[str, Any]) -> str:
        parts = [f"ID: {partner.get('id')}", f"Name: {partner.get('name') or '-'}"]
        if partner.get("email"):
            parts.append(f"Email: {partner.get('email')}")
        if partner.get("phone"):
            parts.append(f"Phone: {partner.get('phone')}")
        return " | ".join(parts)

    has_id = partner_id is not None
    has_name = bool(partner_name and str(partner_name).strip())

    if max_results <= 0:
        return {"ok": False, "error": "max_results must be greater than 0."}

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
            partner = await asyncio.to_thread(client.read_partner, record_id=partner_id)
            partners = [partner]
        else:
            name = str(partner_name).strip()
            await ctx.info(f"Searching partner by name: {name}")
            matches = await asyncio.to_thread(
                client.search_partners,
                filters={"domain": [["name", "ilike", name]]},
                limit=max_results,
            )
            if not matches:
                return {
                    "ok": False,
                    "error": f"No partner found with name '{name}'.",
                }
            partners = matches
            partner = partners[0]

        if has_name:
            partner_ids = [p.get("id") for p in partners]
            await ctx.info(f"Found {len(partners)} partner(s) with IDs: {partner_ids}")
        else:
            await ctx.info(f"Partner fetched — id {partner.get('id')}")

        if has_name:
            response_lines = [f"Found {len(partners)} partner(s) matching '{name}':"]
            for item in partners:
                response_lines.append(f"- {_format_partner_line(item)}")
            response_text = "\n".join(response_lines)
        else:
            response_text = f"Partner found: {_format_partner_line(partner)}"

        return {
            "ok": True,
            "message": "Partner data fetched successfully",
            "response": response_text,
            "summary": {
                "id": partner.get("id"),
                "name": partner.get("name"),
                "email": partner.get("email"),
                "phone": partner.get("phone"),
                "is_company": partner.get("is_company"),
                "customer_rank": partner.get("customer_rank"),
                "supplier_rank": partner.get("supplier_rank"),
            },
            "count": len(partners),
            "partners": partners,
            "partner": partner,
            "data": partner,
        }
    except OdooClientError as exc:
        await ctx.warning(f"Odoo error: {exc}")
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        await ctx.warning(f"Unexpected error: {exc}")
        return {"ok": False, "error": f"Unexpected error: {exc}"}
