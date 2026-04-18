import json
from fastapi import APIRouter, Request
from app.schemas.invoice_schema import InvoiceConfirmRequest

router = APIRouter(prefix="/invoice", tags=["invoice"])


@router.post("/confirm")
async def confirm_invoice(request: Request, payload: InvoiceConfirmRequest):
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