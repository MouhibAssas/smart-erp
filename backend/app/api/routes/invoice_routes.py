import json
from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy.orm import Session
from app.schemas.invoice_schema import InvoiceConfirmRequest
from app.database.session import get_db
from app.middleware.dependencies import get_current_user
from app.models.user import User
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/invoice", tags=["invoice"])


@router.get("/partners/search")
async def search_invoice_partners(
    request: Request,
    name: str = Query(..., min_length=1, description="Partner name to search with ilike"),
    role: str = Query("any", description="Filter role: customer, vendor, any"),
    limit: int = Query(8, ge=1, le=25, description="Maximum number of candidates"),
):
    normalized_role = (role or "any").strip().lower()
    if normalized_role not in {"customer", "vendor", "any"}:
        return {
            "ok": False,
            "error": "role must be one of: customer, vendor, any",
            "partners": [],
            "count": 0,
        }

    tool_result = await request.app.state.agent._call_tool(
        "get_partner",
        {
            "partner_name": name.strip(),
            "max_results": limit,
        },
    )

    if not isinstance(tool_result, dict) or not tool_result.get("ok"):
        return {
            "ok": False,
            "error": (tool_result or {}).get("error", "Partner lookup failed."),
            "partners": [],
            "count": 0,
        }

    candidates = tool_result.get("partners") or []
    if normalized_role == "customer":
        candidates = [p for p in candidates if (p or {}).get("customer_rank", 0) > 0]
    elif normalized_role == "vendor":
        candidates = [p for p in candidates if (p or {}).get("supplier_rank", 0) > 0]

    return {
        "ok": True,
        "query": name,
        "role": normalized_role,
        "count": len(candidates),
        "partners": candidates,
    }


@router.post("/confirm")
async def confirm_invoice(
    request: Request,
    payload: InvoiceConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv_service = ConversationService(db)
    conv_service.get_conversation(payload.conversation_id, current_user.id)

    if payload.partner_id <= 0:
        failed_message = "Invoice creation failed."
        conv_service.add_message(payload.conversation_id, "ai", failed_message)
        return {
            "status": "failed",
            "invoice_type": payload.invoice_type,
            "validated_invoice": payload.model_dump(mode="json"),
            "tool_result": None,
            "message": failed_message,
            "error": "partner_id is required and must be a positive integer selected from partner search results.",
        }

    # Pydantic already validated the payload before we get here.
    canonical = payload.model_dump(mode="json")

    # Call create_invoice directly — no LLM decision loop.
    # The MCP server resolves partner names and account IDs internally.
    result = await request.app.state.agent._call_tool(
        "create_invoice",
        {"invoice_payload": json.dumps(canonical, ensure_ascii=False)},
    )

    created = isinstance(result, dict) and result.get("ok") is True
    invoice_id = None
    if created and isinstance(result, dict):
        invoice_id = result.get("invoice_id")
        if invoice_id is None:
            invoice = result.get("invoice") or {}
            invoice_id = invoice.get("id") if isinstance(invoice, dict) else None

    message = (
        f"Invoice created in Odoo — ID {invoice_id}"
        if created and invoice_id is not None
        else result.get("message")
        if isinstance(result, dict) and result.get("message")
        else "Invoice confirmed and created successfully in Odoo."
        if created
        else "Invoice creation failed."
    )

    conv_service.add_message(payload.conversation_id, "ai", message)

    return {
        "status":           "created" if created else "failed",
        "invoice_type":     payload.invoice_type,
        "validated_invoice": canonical,
        "tool_result":      result,
        "message":          message,
        "error":            result.get("error") if (result and not created) else None,
    }