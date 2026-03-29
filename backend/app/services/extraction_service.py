import json
import logging

from sqlalchemy import JSON
from app.services.ocr_service import OCRProcessor
from app.schemas.invoice_schema import CanonicalInvoice
from app.llm.factory import get_llm

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """
You are an invoice data extraction assistant.
Given raw OCR text from an invoice document, return ONLY a valid JSON object.
No prose, no explanation, no markdown fences — just the JSON.

Use this exact structure:
{
  "invoice_number": "string or null",
  "invoice_date": "YYYY-MM-DD or JSON null (not the string 'null')",
  "due_date": "YYYY-MM-DD or JSON null (not the string 'null')",
  "currency": "string, default TND",
  "vendor": {
    "name": "string",
    "address": "string or null",
    "tax_id": "string or null",
    "iban": "string or null"
  },
  "buyer": {
    "name": "string",
    "address": "string or null",
    "tax_id": "string or null"
  },
  "lines": [
    {
      "description": "string",
      "quantity": 1.0,
      "unit_price": 0.0,
            "discount": 0.0,
      "tax_rate": 0.0,
      "line_total": 0.0
    }
  ],
  "totals": {
    "subtotal": 0.0,
    "tax_amount": 0.0,
    "discount": 0.0,
    "total_due": 0.0
  },
  "payment_terms": "string or null",
  "notes": "string or null",
  "confidence_score": 0.95,
  "missing_fields": ["field_path", ...]
}

Rules:
- confidence_score: 0.0 to 1.0 — your honest assessment of extraction quality
- missing_fields: list every field you could not find, e.g. ["due_date", "vendor.tax_id"]
- lines must always be an array, even for a single line item
- All numeric fields must be numbers, not strings
- vendor is the company ISSUING the invoice (seller), buyer is the RECIPIENT (customer)
- If vendor information is not visible in the document, set vendor fields to null and add them to missing_fields
- capture per-line discount percent in lines[].discount (0 to 100)
"""


class ExtractionService:
    def __init__(self):
        self.ocr = OCRProcessor()
        self.llm = get_llm()

    async def extract_from_file(
        self, file_bytes: bytes, filename: str
    ) -> CanonicalInvoice:
        """
        Full pipeline: bytes → OCR raw text → LLM structuring → CanonicalInvoice
        Raises ValueError if JSON parsing or Pydantic validation fails.
        """
        # Step 1 — OCR
        logger.info(f"Starting OCR for file: {filename}")
        ocr_result = self.ocr.extract_from_bytes(file_bytes, filename)
        raw_text = ocr_result["raw_text"]
        ocr_confidence = ocr_result["confidence"]
        logger.info(f"OCR complete. Pages: {ocr_result['page_count']}, confidence: {ocr_confidence:.2%}")

        if not raw_text.strip():
            raise ValueError("OCR returned empty text — file may be unreadable or blank.")

        # Step 2 — LLM structuring
        logger.info("Sending OCR text to extraction LLM...")
        messages = [
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user",   "content": f"OCR text:\n\n{raw_text}"}
        ]
        raw_response = await self.llm.generate(messages)

        # Step 3 — Parse JSON safely
        try:
            # Strip accidental markdown fences if LLM adds them despite instructions
            clean = raw_response.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            data = json.loads(clean.strip())
            data = _fix_null_strings(data)

        except json.JSONDecodeError as e:
            logger.error(f"LLM returned invalid JSON: {e}\nRaw: {raw_response[:500]}")
            raise ValueError(f"Extraction LLM returned invalid JSON: {e}")

        # Step 4 — Validate with Pydantic
        try:
            canonical = CanonicalInvoice(**data)
        except Exception as e:
            logger.error(f"CanonicalInvoice validation failed: {e}")
            raise ValueError(f"Extracted data failed schema validation: {e}")

        logger.info(
            f"Extraction complete. Confidence: {canonical.confidence_score}, "
            f"Missing fields: {canonical.missing_fields}"
        )
        return canonical
def _fix_null_strings(obj):
    """Recursively replace string 'null' with None in parsed JSON."""
    if isinstance(obj, dict):
        return {k: _fix_null_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_fix_null_strings(i) for i in obj]
    if obj == "null" or obj == "None":
        return None
    return obj
