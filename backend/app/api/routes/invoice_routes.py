from fastapi import APIRouter

from app.schemas.invoice_schema import InvoiceConfirmRequest

router = APIRouter(prefix="/invoice", tags=["invoice"])


@router.post("/confirm")
async def confirm_invoice(payload: InvoiceConfirmRequest):
	# FastAPI + Pydantic validate CanonicalInvoice fields and invoice_type before this runs.
	return {
		"status": "validated",
		"invoice_type": payload.invoice_type,
		"invoice": payload.model_dump(mode="json"),
	}
