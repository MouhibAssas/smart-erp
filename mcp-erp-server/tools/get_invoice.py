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


async def get_invoice(
	record_id: Annotated[int, Field(
		description=(
			"Odoo invoice integer ID to read from account.move. "
			"Example: 125"
		)
	)],
	ctx: Context,
) -> Dict[str, Any]:
	"""Read one invoice/vendor bill in Odoo by record ID."""

	try:
		client = _get_client(ctx)
	except RuntimeError as exc:
		return {"ok": False, "error": str(exc)}

	await ctx.info(f"Reading invoice id={record_id}")

	try:
		invoice = client.read_invoice(record_id=record_id)
		await ctx.info(f"Invoice fetched — id {invoice.get('id')}")
		partner = invoice.get("partner_id")
		partner_label = None
		if isinstance(partner, list) and len(partner) > 1:
			partner_label = partner[1]

		response_lines = [
			f"Invoice #{invoice.get('name') or invoice.get('id')} details:",
		]
		if invoice.get("state"):
			response_lines.append(f"- State: {invoice.get('state')}")
		if partner_label:
			response_lines.append(f"- Partner: {partner_label}")
		if invoice.get("amount_total") is not None:
			response_lines.append(f"- Total: {invoice.get('amount_total')}")
		if invoice.get("amount_residual") is not None:
			response_lines.append(f"- Residual: {invoice.get('amount_residual')}")
		if invoice.get("payment_state"):
			response_lines.append(f"- Payment state: {invoice.get('payment_state')}")
		if invoice.get("invoice_date"):
			response_lines.append(f"- Invoice date: {invoice.get('invoice_date')}")
		if invoice.get("invoice_date_due"):
			response_lines.append(f"- Due date: {invoice.get('invoice_date_due')}")

		return {
			"ok": True,
			"message": "Invoice data fetched successfully",
			"response": "\n".join(response_lines),
			"summary": {
				"id": invoice.get("id"),
				"name": invoice.get("name"),
				"state": invoice.get("state"),
				"amount_total": invoice.get("amount_total"),
				"partner": partner_label,
			},
			"data": invoice,
			"invoice": invoice,
		}
	except OdooClientError as exc:
		await ctx.warning(f"Odoo error: {exc}")
		return {"ok": False, "error": str(exc)}
	except Exception as exc:
		await ctx.warning(f"Unexpected error: {exc}")
		return {"ok": False, "error": f"Unexpected error: {exc}"}
