import asyncio
import logging
from datetime import date, datetime
from typing import Annotated, Any, Dict, List, Optional

from fastmcp import Context
from pydantic import Field

from clients.odoo_client import OdooClientError, OdooSessionClient

logger = logging.getLogger(__name__)


def _get_client(ctx: Context) -> OdooSessionClient:
    client = (ctx.lifespan_context or {}).get("odoo")
    if not isinstance(client, OdooSessionClient):
        raise RuntimeError("Odoo client not found in lifespan context.")
    return client


async def search_invoices_advanced(
    move_type: Annotated[
        Optional[str],
        Field(description=(
            "Filter by invoice direction: "
            "'out_invoice' (customer invoices), "
            "'in_invoice' (vendor bills), "
            "or omit for both."
        )),
    ] = None,
    state: Annotated[
        Optional[str],
        Field(description=(
            "Filter by Odoo state: "
            "'draft' (not yet confirmed), "
            "'posted' (confirmed/open), "
            "'cancel' (cancelled). "
            "Omit to return all states."
        )),
    ] = None,
    payment_state: Annotated[
        Optional[str],
        Field(description=(
            "Filter by payment status (only meaningful for posted invoices): "
            "'not_paid', 'partial', 'paid', 'reversed'. "
            "Special value 'overdue' returns posted+not_paid invoices whose due date is in the past."
        )),
    ] = None,
    date_from: Annotated[
        Optional[str],
        Field(description="Filter invoices with invoice_date >= this date. Format: YYYY-MM-DD."),
    ] = None,
    date_to: Annotated[
        Optional[str],
        Field(description="Filter invoices with invoice_date <= this date. Format: YYYY-MM-DD."),
    ] = None,
    partner_name: Annotated[
        Optional[str],
        Field(description="Filter by partner name (case-insensitive partial match)."),
    ] = None,
    limit: Annotated[
        int,
        Field(description="Maximum number of invoices to return (1–200). Default 50."),
    ] = 50,
    count_only: Annotated[
        bool,
        Field(description=(
            "If true, return only the total matching count — no invoice records. "
            "Much faster when you only need KPI counts."
        )),
    ] = False,
    ctx: Context = None,
) -> Dict[str, Any]:
    """
    Flexible invoice search for dashboard KPIs and reporting.
    Supports filtering by type, state, payment status, date range, and partner.
    Use count_only=true for fast KPI counts without transferring full records.
    """

    # ── validate inputs ───────────────────────────────────────────────────────
    valid_move_types    = {None, "out_invoice", "in_invoice"}
    valid_states        = {None, "draft", "posted", "cancel"}
    valid_payment_states = {None, "not_paid", "partial", "paid", "reversed", "overdue"}

    if move_type not in valid_move_types:
        return {"ok": False, "error": f"move_type must be one of: out_invoice, in_invoice (or omit)."}
    if state not in valid_states:
        return {"ok": False, "error": f"state must be one of: draft, posted, cancel (or omit)."}
    if payment_state not in valid_payment_states:
        return {"ok": False, "error": f"payment_state must be one of: not_paid, partial, paid, reversed, overdue (or omit)."}
    if limit < 1 or limit > 200:
        return {"ok": False, "error": "limit must be between 1 and 200."}
    if date_from:
        try:
            datetime.strptime(date_from, "%Y-%m-%d")
        except ValueError:
            return {"ok": False, "error": "date_from must be in YYYY-MM-DD format."}
    if date_to:
        try:
            datetime.strptime(date_to, "%Y-%m-%d")
        except ValueError:
            return {"ok": False, "error": "date_to must be in YYYY-MM-DD format."}
    if date_from and date_to and date_from > date_to:
        return {"ok": False, "error": "date_from cannot be later than date_to."}

    try:
        client = _get_client(ctx)
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}

    try:
        # ── build Odoo domain ─────────────────────────────────────────────────
        domain: List[Any] = []

        # move_type
        if move_type:
            domain.append(["move_type", "=", move_type])
        else:
            # exclude journal entries, receipts etc — only invoices/bills
            domain.append(["move_type", "in", ["out_invoice", "in_invoice"]])

        # state
        if payment_state == "overdue":
            # overdue = posted + not_paid + due date in the past
            today_str = date.today().isoformat()
            domain.append(["state", "=", "posted"])
            domain.append(["payment_state", "in", ["not_paid", "partial"]])
            domain.append(["invoice_date_due", "<", today_str])
            domain.append(["invoice_date_due", "!=", False])
        else:
            if state:
                domain.append(["state", "=", state])
            if payment_state:
                domain.append(["payment_state", "=", payment_state])

        # date range
        if date_from:
            domain.append(["invoice_date", ">=", date_from])
        if date_to:
            domain.append(["invoice_date", "<=", date_to])

        # partner
        if partner_name and str(partner_name).strip():
            domain.append(["partner_id.name", "ilike", str(partner_name).strip()])

        await ctx.info(
            f"search_invoices_advanced: move_type={move_type} state={state} "
            f"payment_state={payment_state} date_from={date_from} date_to={date_to} "
            f"limit={limit} count_only={count_only}"
        )

        # ── fetch count and records ───────────────────────────────────────────
        records: List[Dict[str, Any]] = []
        if count_only:
            total_matching = await asyncio.to_thread(
                client.count_invoices,
                filters={"domain": domain},
                model="account.move",
            )
        else:
            total_matching, records = await asyncio.gather(
                asyncio.to_thread(
                    client.count_invoices,
                    filters={"domain": domain},
                    model="account.move",
                ),
                asyncio.to_thread(
                    client.search_invoices,
                    filters={"domain": domain},
                    limit=limit,
                    model="account.move",
                ),
            )

        # ── compute summary ───────────────────────────────────────────────────
        total_amount    = 0.0
        total_residual  = 0.0
        for rec in records:
            amt = rec.get("amount_total")
            res = rec.get("amount_residual")
            if isinstance(amt, (int, float)):
                total_amount += float(amt)
            if isinstance(res, (int, float)):
                total_residual += float(res)

        summary = {
            "count":          total_matching,
            "count_returned": len(records),
            "total_amount":   round(total_amount,   2),
            "total_residual": round(total_residual, 2),
            "filters_used": {
                "move_type":     move_type,
                "state":         state,
                "payment_state": payment_state,
                "date_from":     date_from,
                "date_to":       date_to,
                "partner_name":  partner_name,
            },
        }

        await ctx.info(
            f"Found {total_matching} matching invoices (returned={len(records)}) | "
            f"total={total_amount:.2f} residual={total_residual:.2f}"
        )

        # ── return ────────────────────────────────────────────────────────────
        if count_only:
            return {
                "ok":      True,
                "message": f"Found {total_matching} invoice(s)",
                "response": f"Found {total_matching} invoice(s) matching your filters.",
                "summary": summary,
            }

        # Build a human-readable response listing each invoice
        response_lines = [f"Found {total_matching} invoice(s) (showing {len(records)}):"]
        for inv in records:
            partner = inv.get("partner_id")
            partner_label = partner[1] if isinstance(partner, list) and len(partner) > 1 else "-"
            response_lines.append(
                f"- {inv.get('name') or inv.get('id')} | "
                f"Partner: {partner_label} | "
                f"Date: {inv.get('invoice_date') or '-'} | "
                f"Due: {inv.get('invoice_date_due') or '-'} | "
                f"Total: {inv.get('amount_total')} | "
                f"Residual: {inv.get('amount_residual')} | "
                f"Status: {inv.get('payment_state') or inv.get('state') or '-'}"
            )

        return {
            "ok":      True,
            "message": f"Found {total_matching} invoice(s)",
            "response": "\n".join(response_lines),
            "summary": summary,
            "invoices": records,
        }

    except OdooClientError as exc:
        await ctx.warning(f"Odoo error: {exc}")
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        await ctx.warning(f"Unexpected error: {exc}")
        return {"ok": False, "error": f"Unexpected error: {exc}"}