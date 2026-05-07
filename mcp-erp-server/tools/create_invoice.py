import asyncio
import json
import logging
import re
from typing import Annotated, Any, Dict

from fastmcp import Context
from pydantic import Field

from clients.odoo_client import OdooClientError, OdooSessionClient


logger = logging.getLogger(__name__)


def _get_client(ctx: Context) -> OdooSessionClient:
    client = (ctx.lifespan_context or {}).get("odoo")
    if not isinstance(client, OdooSessionClient):
        raise RuntimeError(
            "Odoo client not found in lifespan context. "
            "Is the MCP server running correctly?"
        )
    return client


def _resolve_partner_id(client: OdooSessionClient, name: str) -> int:
    """
    Searches Odoo for a partner by name.
    Returns their integer ID.
    Raises OdooClientError with a clear message if not found.
    """
    results = client.search_invoices(
        filters={"domain": [["name", "ilike", name], ["is_company", "=", True]]},
        limit=1,
        model="res.partner",
    )
    if results:
        return int(results[0]["id"])

    # Try without is_company restriction
    results = client.search_invoices(
        filters={"domain": [["name", "ilike", name]]},
        limit=1,
        model="res.partner",
    )
    if results:
        return int(results[0]["id"])

    raise OdooClientError(
        f"Partner '{name}' not found in Odoo. "
        f"Please create this contact first: Odoo → Contacts → New."
    )


def _resolve_default_account(client: OdooSessionClient, move_type: str) -> int:
    """
    Finds a default income or expense account for invoice lines.
    Searches for the first usable account of the right type.
    """
    account_types = (
        ["income", "income_other"]
        if move_type == "out_invoice"
        else ["expense", "expense_depreciation", "expense_direct_cost"]
    )
    results = client.search_invoices(
        filters={"domain": [["account_type", "in", account_types]]},
        limit=1,
        model="account.account",
    )
    if results:
        return int(results[0]["id"])

    # Fallback for databases with custom account_type values.
    results = client.search_invoices(
        filters={"domain": []},
        limit=1,
        model="account.account",
    )
    if results:
        return int(results[0]["id"])

    raise OdooClientError(
        f"No default account found for move_type '{move_type}' in Odoo. "
        f"Check your Chart of Accounts: Accounting → Configuration → Chart of Accounts."
    )


def _resolve_product_id(client: OdooSessionClient, product_name: str) -> int | None:
    """Resolve a product.product record by direct case-insensitive name match."""
    if not product_name or not isinstance(product_name, str):
        return None

    results = client.search_invoices(
        filters={"domain": [["name", "ilike", product_name]]},
        limit=1,
        model="product.product",
    )
    if not results:
        return None

    product_id = results[0].get("id")
    return int(product_id) if isinstance(product_id, int) else None


def _resolve_tax_ids_for_rate(
    client: OdooSessionClient,
    move_type: str,
    tax_rate: Any,
) -> list[int]:
    """Resolve a single best Odoo tax ID from a canonical tax percentage."""
    if tax_rate is None:
        return []

    try:
        rate = float(tax_rate)
    except (TypeError, ValueError):
        return []

    if rate <= 0:
        return []

    tax_use = "sale" if move_type == "out_invoice" else "purchase"
    domain = [["type_tax_use", "=", tax_use], ["amount", "=", rate], ["active", "=", True]]
    results = client.search_invoices(
        filters={"domain": domain},
        limit=50,
        model="account.tax",
    )

    if not results:
        return []

    def score_tax(rec: Dict[str, Any]) -> int:
        name = str(rec.get("name") or "").lower()
        score = 0

        # Keep active taxes as primary candidates.
        if rec.get("active") is True:
            score += 50

        # Prefer taxes that explicitly mention the requested rate in their label.
        rate_token = str(int(rate)) if float(rate).is_integer() else str(rate)
        if rate_token in name:
            score += 10

        # Heuristics for common accounting tax naming.
        if move_type == "in_invoice":
            if any(k in name for k in ("purchase", "supplier", "vendor", "achat", "fourn")):
                score += 8
        else:
            if any(k in name for k in ("sale", "customer", "client", "vente")):
                score += 8

        # De-prioritize special taxes that users typically do not want auto-assigned.
        if any(k in name for k in ("asset", "olp", "withholding", "retention", "immobil")):
            score -= 20

        return score

    best = max(results, key=score_tax)
    best_id = best.get("id") if isinstance(best, dict) else None

    if len(results) > 1:
        logger.info(
            "Multiple taxes matched rate=%s use=%s; selected one tax id=%s name=%s from %d candidates",
            rate,
            tax_use,
            best_id,
            best.get("name") if isinstance(best, dict) else None,
            len(results),
        )

    return [int(best_id)] if isinstance(best_id, int) else []


def _resolve_payment_term_id(client: OdooSessionClient, term_name: str) -> int | None:
    """
    Searches Odoo for a payment term by name.
    Returns the integer ID or None if not found.
    """
    if not term_name or not isinstance(term_name, str):
        return None

    def normalize(text: str) -> str:
        return " ".join(text.strip().lower().split())

    def normalized_key(text: str) -> str:
        return re.sub(r"[^a-z0-9]", "", normalize(text))

    def extract_int_tokens(text: str) -> set[str]:
        return set(re.findall(r"\d+", text))

    normalized = normalize(term_name)
    target_key = normalized_key(term_name)
    target_nums = extract_int_tokens(normalized)

    try:
        search_domains = [
            [["name", "=", term_name]],
            [["name", "=", normalized]],
            [["name", "ilike", term_name]],
            [["name", "ilike", normalized]],
        ]

        candidates: list[Dict[str, Any]] = []
        seen_ids: set[int] = set()

        for domain in search_domains:
            results = client.search_invoices(
                filters={"domain": domain},
                limit=20,
                model="account.payment.term",
            )
            for record in results:
                record_id = record.get("id")
                if isinstance(record_id, int) and record_id not in seen_ids:
                    candidates.append(record)
                    seen_ids.add(record_id)

        if not candidates:
            return None

        # 1) Strongest match: normalized key equality (e.g. "15 Days" == "15days")
        exact_key_matches = [
            r for r in candidates
            if normalized_key(str(r.get("name") or "")) == target_key
        ]
        if exact_key_matches:
            chosen = exact_key_matches[0]
            logger.info(
                "Payment term exact-key match: input='%s' -> id=%s name=%s",
                term_name,
                chosen.get("id"),
                chosen.get("name"),
            )
            return int(chosen["id"])

        # 2) If input has numeric tokens (15, 30, ...), keep only candidates with same numbers.
        if target_nums:
            filtered = []
            for record in candidates:
                name = normalize(str(record.get("name") or ""))
                if extract_int_tokens(name) == target_nums:
                    filtered.append(record)
            if filtered:
                candidates = filtered

        def score(record: Dict[str, Any]) -> int:
            name = normalize(str(record.get("name") or ""))
            score_value = 0
            if name == normalized:
                score_value += 100
            if term_name.strip().lower() in name:
                score_value += 50
            if normalized in name:
                score_value += 40
            if target_nums:
                name_nums = extract_int_tokens(name)
                if name_nums == target_nums:
                    score_value += 30
                elif name_nums & target_nums:
                    score_value += 25
            if "days" in normalized and "days" in name:
                score_value += 15
            if record.get("active") is True:
                score_value += 5
            return score_value

        best = max(candidates, key=score)
        logger.info(
            "Payment term selected: input='%s' -> id=%s name=%s",
            term_name,
            best.get("id"),
            best.get("name"),
        )
        return int(best["id"])
    except Exception:
        pass
    
    return None


def _calculate_due_date_from_payment_term(
    client: OdooSessionClient,
    invoice_date: str | None,
    payment_term_name: str | None,
) -> str | None:
    """
    Calculate due date from payment terms.
    If payment_term_name provided, look it up in Odoo and compute due date.
    Fallback: add standard net terms (30 days) if no specific term found.
    Returns YYYY-MM-DD or None.
    """
    if not invoice_date or not payment_term_name:
        return None
    
    from datetime import datetime, timedelta
    
    try:
        inv_date = datetime.strptime(invoice_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    
    # Try to find payment term in Odoo
    term_id = _resolve_payment_term_id(client, payment_term_name)
    
    if term_id:
        try:
            # Get payment term details
            term_records = client.search_invoices(
                filters={"domain": [["id", "=", term_id]]},
                limit=1,
                model="account.payment.term",
            )
            if term_records:
                term = term_records[0]
                # Odoo payment terms have lines with days offsets
                # For simplicity, if no lines, assume 30 days net
                days = 30
                if "line_ids" in term or "lines" in term:
                    # Extract days from first line if available
                    lines = term.get("line_ids") or term.get("lines") or []
                    if lines:
                        # Typically last line has the days offset
                        try:
                            days = int(lines[-1].get("days", 30))
                        except (ValueError, IndexError, TypeError):
                            days = 30
                
                due_date = inv_date + timedelta(days=days)
                return due_date.strftime("%Y-%m-%d")
        except Exception:
            pass
    
    # Fallback: add standard 30 days if we have payment_terms text
    elif "net" in payment_term_name.lower() or "30" in payment_term_name:
        try:
            due_date = inv_date + timedelta(days=30)
            return due_date.strftime("%Y-%m-%d")
        except Exception:
            pass
    
    return None


def _build_odoo_vals(
    client: OdooSessionClient,
    raw: Dict[str, Any],
    partner_id: int,
    default_account_id: int,
) -> Dict[str, Any]:
    """
    Converts canonical invoice fields into Odoo ORM create vals.
    Handles both canonical shape (from OCR) and direct Odoo shape.
    """
    move_type = raw.get("move_type") or raw.get("invoice_type", "out_invoice")

    # Build invoice lines from canonical shape
    lines = raw.get("lines") or raw.get("invoice_line_ids") or []
    invoice_line_ids = []

    for line in lines:
        # Support both canonical line shape and raw Odoo shape
        if isinstance(line, list):
            # Already in ORM Command format [0, 0, {...}]
            invoice_line_ids.append(line)
        else:
            product_name = (
                line.get("description")
                or line.get("name")
                or "Service"
            )
            product_id = _resolve_product_id(client, str(product_name))

            if product_id:
                line_vals = {
                    "product_id": product_id,
                    "quantity": float(line.get("quantity") or 1),
                    "price_unit": float(line.get("unit_price") or line.get("price_unit") or 0),
                }
                if line.get("discount") not in (None, "null", ""):
                    line_vals["discount"] = float(line.get("discount") or 0)
                invoice_line_ids.append([0, 0, line_vals])
                continue

            tax_ids = line.get("tax_ids") or _resolve_tax_ids_for_rate(
                client,
                move_type,
                line.get("tax_rate"),
            )
            line_vals = {
                "name":       product_name,
                "quantity":   float(line.get("quantity") or 1),
                "price_unit": float(line.get("unit_price") or line.get("price_unit") or 0),
                "account_id": int(line.get("account_id") or default_account_id),
                "discount":   float(line.get("discount") or 0),
            }
            if tax_ids:
                line_vals["tax_ids"] = [[6, 0, [int(t) for t in tax_ids]]]
            invoice_line_ids.append([0, 0, line_vals])

    vals: Dict[str, Any] = {
        "move_type":        move_type,
        "partner_id":       partner_id,
        "invoice_line_ids": invoice_line_ids,
    }

    # Handle invoice_date
    invoice_date = raw.get("invoice_date")
    if invoice_date and invoice_date not in (None, "null", ""):
        vals["invoice_date"] = invoice_date

    # Payment terms and due date are mutually exclusive:
    # - If payment terms are provided, Odoo computes due date from term rules.
    # - If due date is provided (and no payment terms), use explicit due date.
    due_date = raw.get("due_date")
    payment_terms = raw.get("payment_terms")
    has_payment_terms = bool(payment_terms and payment_terms not in (None, "null", ""))
    has_due_date = bool(due_date and due_date not in (None, "null", ""))

    if has_payment_terms:
        term_id = _resolve_payment_term_id(client, str(payment_terms))
        if not term_id:
            raise OdooClientError(
                f"Payment term '{payment_terms}' was not found in Odoo. "
                "Please select an existing payment term from Accounting configuration."
            )
        vals["invoice_payment_term_id"] = int(term_id)
        logger.info("Using invoice_payment_term_id=%s for payment_terms='%s'", term_id, payment_terms)
        # Do not send explicit due date when payment terms are provided.
        vals.pop("invoice_date_due", None)
    elif has_due_date:
        vals["invoice_date_due"] = due_date

    # Handle optional fields (skip if None or "null" string)
    for src, dst in [
        ("invoice_number","ref"),
        ("ref",           "ref"),
        ("journal_id",    "journal_id"),
        ("currency_id",   "currency_id"),
        ("narration",     "narration"),
    ]:
        value = raw.get(src)
        if value and value not in (None, "null", ""):
            vals[dst] = value

    # Use canonical notes as fallback narration, but do not override explicit narration.
    notes_value = raw.get("notes")
    if (
        notes_value
        and notes_value not in (None, "null", "")
        and not vals.get("narration")
    ):
        vals["narration"] = notes_value

    return vals


async def create_invoice(
    invoice_payload: Annotated[str, Field(
        description=(
            "JSON string representing an invoice. Accepts two shapes:\n\n"
            "CANONICAL shape (from OCR extraction):\n"
            "  move_type        : 'out_invoice' (customer) or 'in_invoice' (vendor)\n"
            "  partner_id       : integer Odoo partner ID (required for confirmation flow)\n"
            "  vendor           : {name, address, tax_id}  — who issued the invoice\n"
            "  buyer            : {name, address}           — who receives it\n"
            "  lines            : [{description, quantity, unit_price}]\n"
            "  invoice_date     : 'YYYY-MM-DD' (optional)\n"
            "  due_date         : 'YYYY-MM-DD' (optional)\n"
            "  invoice_number   : string (optional)\n\n"
            "ODOO shape (direct):\n"
            "  move_type        : 'out_invoice' or 'in_invoice'\n"
            "  partner_id       : integer Odoo partner ID\n"
            "  invoice_line_ids : [[0,0,{name,quantity,price_unit,account_id}]]\n\n"
            "Example canonical: {\"move_type\":\"out_invoice\","
            "\"partner_id\":42,"
            "\"buyer\":{\"name\":\"ACME\"},"
            "\"lines\":[{\"description\":\"Consulting\",\"quantity\":1,\"unit_price\":500}]}"
        )
    )],
    ctx: Context,
) -> Dict[str, Any]:
    """Create a customer invoice or vendor bill in Odoo from canonical or direct input."""

    # ── Step 1: parse JSON ────────────────────────────────────────────
    try:
        raw = json.loads(invoice_payload)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"Invalid JSON: {exc}"}

    if not isinstance(raw, dict):
        return {"ok": False, "error": "invoice_payload must be a JSON object"}

    # ── Step 2: determine move_type ───────────────────────────────────
    move_type = raw.get("move_type") or raw.get("invoice_type", "out_invoice")
    if move_type not in ("out_invoice", "in_invoice"):
        return {
            "ok": False,
            "error": "move_type must be 'out_invoice' (customer) or 'in_invoice' (vendor)",
        }

    # ── Step 3: get Odoo client ───────────────────────────────────────
    try:
        client = _get_client(ctx)
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}

    try:
        await ctx.info(f"Creating {move_type} invoice")

        # ── Step 4: require partner_id from explicit partner selection ─────────
        partner_id = raw.get("partner_id")
        if not isinstance(partner_id, int) or partner_id <= 0:
            return {
                "ok": False,
                "error": (
                    "partner_id is required from partner selection. "
                    "Name-based partner resolution is disabled for this flow."
                ),
            }

        await ctx.info(f"Using provided partner_id={partner_id}")

        # ── Step 5: resolve default account for lines ─────────────────
        # Only needed if lines don't already have account_id
        lines = raw.get("lines") or raw.get("invoice_line_ids") or []
        if not lines:
            return {"ok": False, "error": "Invoice must have at least one line."}

        needs_account = any(
            not isinstance(line, list) and not line.get("account_id")
            for line in lines
        )
        default_account_id = 0
        if needs_account:
            await ctx.info("Resolving default account_id for lines")
            default_account_id = await asyncio.to_thread(_resolve_default_account, client, move_type)
            await ctx.info(f"Default account_id={default_account_id}")

        # ── Step 6: build vals and create ─────────────────────────────
        vals = await asyncio.to_thread(_build_odoo_vals, client, raw, partner_id, default_account_id)
        record_id = await asyncio.to_thread(client.create_invoice, vals=vals)
        record = await asyncio.to_thread(client.read_invoice, record_id=record_id)

        await ctx.info(f"Invoice created: id={record_id} name={record.get('name')}")
        return {
            "ok": True,
            "message": f"Invoice created in Odoo — ID {record_id}",
            "invoice": record,
            "invoice_id": record_id,
        }

    except OdooClientError as exc:
        await ctx.warning(f"Odoo error: {exc}")
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        await ctx.warning(f"Unexpected error: {exc}")
        return {"ok": False, "error": f"Unexpected error: {exc}"}