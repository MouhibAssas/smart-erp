from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import date


class InvoiceLine(BaseModel):
    description: str = ""
    quantity: Optional[float] = 0.0
    unit_price: Optional[float] = 0.0
    discount: Optional[float] = 0.0
    tax_rate: Optional[float] = 0.0
    line_total: Optional[float] = 0.0


class InvoiceParty(BaseModel):
    name: Optional[str] = None  # ← was: name: str
    address: Optional[str] = None
    tax_id: Optional[str] = None
    iban: Optional[str] = None


class InvoiceTotals(BaseModel):
    subtotal: Optional[float] = 0.0
    tax_amount: Optional[float] = 0.0
    discount: Optional[float] = Field(default=0.0)  # ← was: float = Field(...)
    total_due: Optional[float] = 0.0

class CanonicalInvoice(BaseModel):
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    currency: str = "TND"
    vendor: Optional[InvoiceParty] = None   # changed
    buyer: Optional[InvoiceParty] = None    # changed
    lines: list[InvoiceLine] = []
    totals: Optional[InvoiceTotals] = None  # changed
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    confidence_score: float = 0.0
    missing_fields: list[str] = []


class InvoiceConfirmRequest(CanonicalInvoice):
    # Odoo move_type compatible values.
    invoice_type: Literal["out_invoice", "in_invoice"]
    partner_id: int
    conversation_id: int
