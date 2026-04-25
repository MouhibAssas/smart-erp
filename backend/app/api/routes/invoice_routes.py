import json
from fastapi import APIRouter, Query, Request
from app.schemas.invoice_schema import InvoiceConfirmRequest

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
async def confirm_invoice(request: Request, payload: InvoiceConfirmRequest):
    if payload.partner_id <= 0:
        return {
            "status": "failed",
            "invoice_type": payload.invoice_type,
            "validated_invoice": payload.model_dump(mode="json"),
            "tool_result": None,
            "message": None,
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

    return {
        "status":           "created" if created else "failed",
        "invoice_type":     payload.invoice_type,
        "validated_invoice": canonical,
        "tool_result":      result,
        "message":          result.get("message") if result else None,
        "error":            result.get("error") if (result and not created) else None,
    }