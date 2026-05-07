import asyncio
from typing import Annotated, Any, Dict, List

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


async def get_unpaid_invoices(
	invoice_type: Annotated[
		str,
		Field(
			description=(
				"Invoice scope: 'customer', 'vendor', or 'both'. "
				"Defaults to 'customer'."
			)
		),
	] = "customer",
	partner_name: Annotated[
		str | None,
		Field(description="Optional partner name filter (case-insensitive)."),
	] = None,
	limit: Annotated[
		int,
		Field(description="Maximum number of unpaid invoices to return."),
	] = 20,
	ctx: Context = None,
) -> Dict[str, Any]:
	"""Get unpaid invoices (posted invoices with residual amount > 0)."""

	normalized_type = (invoice_type or "customer").strip().lower()
	if normalized_type not in {"customer", "vendor", "both"}:
		return {
			"ok": False,
			"error": "invoice_type must be one of: customer, vendor, both.",
		}

	if limit <= 0:
		return {"ok": False, "error": "limit must be greater than 0."}

	try:
		client = _get_client(ctx)
	except RuntimeError as exc:
		return {"ok": False, "error": str(exc)}

	try:
		domain: List[List[Any]] = [
			["state", "=", "posted"],
			["amount_residual", ">", 0],
		]

		if normalized_type == "customer":
			domain.append(["move_type", "=", "out_invoice"])
		elif normalized_type == "vendor":
			domain.append(["move_type", "=", "in_invoice"])
		else:
			domain.append(["move_type", "in", ["out_invoice", "in_invoice"]])

		if partner_name and str(partner_name).strip():
			domain.append(["partner_id.name", "ilike", str(partner_name).strip()])

		await ctx.info(
			f"Searching unpaid invoices type={normalized_type} limit={limit}"
		)

		invoices = await asyncio.to_thread(
			client.search_invoices,
			filters={"domain": domain},
			limit=limit,
			model="account.move",
		)

		total_residual = 0.0
		for inv in invoices:
			residual = inv.get("amount_residual")
			if isinstance(residual, (int, float)):
				total_residual += float(residual)

		await ctx.info(f"Found {len(invoices)} unpaid invoices")

		response_lines = [
			f"Found {len(invoices)} unpaid {normalized_type} invoice(s).",
			f"Total residual amount: {round(total_residual, 2)}",
		]
		for inv in invoices[:5]:
			partner = inv.get("partner_id")
			partner_label = None
			if isinstance(partner, list) and len(partner) > 1:
				partner_label = partner[1]
			line = (
				f"- {inv.get('name') or inv.get('id')}"
				f" | residual={inv.get('amount_residual')}"
				f" | due={inv.get('invoice_date_due')}"
			)
			if partner_label:
				line += f" | partner={partner_label}"
			response_lines.append(line)
		if len(invoices) > 5:
			response_lines.append(f"- ... and {len(invoices) - 5} more")

		return {
			"ok": True,
			"message": "Unpaid invoices fetched successfully",
			"response": "\n".join(response_lines),
			"summary": {
				"count": len(invoices),
				"invoice_type": normalized_type,
				"total_residual": round(total_residual, 2),
				"limit": limit,
			},
			"filters": {
				"invoice_type": normalized_type,
				"partner_name": partner_name,
				"limit": limit,
			},
			"invoices": invoices,
			"data": invoices,
		}
	except OdooClientError as exc:
		await ctx.warning(f"Odoo error: {exc}")
		return {"ok": False, "error": str(exc)}
	except Exception as exc:
		await ctx.warning(f"Unexpected error: {exc}")
		return {"ok": False, "error": f"Unexpected error: {exc}"}
