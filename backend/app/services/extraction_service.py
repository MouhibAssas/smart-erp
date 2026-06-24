import json
import logging

from app.services.ocr_service import OCRProcessor
from app.schemas.invoice_schema import CanonicalInvoice
from app.llm.factory import get_llm

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """
You are an invoice data extraction assistant.
Given raw OCR text from an invoice document, return ONLY a valid JSON object.
No prose, no explanation, no markdown fences, NO COMMENTS — just raw, valid JSON.

**CRITICAL VENDOR vs BUYER DISTINCTION:**
- VENDOR = The company ISSUING/SELLING this invoice (the invoice creator/seller)
  Example context: In a purchase invoice, VENDOR is the supplier selling goods to you
  Fields: name, address, tax_id/MF, IBAN, contact — whoever SENDS the invoice

- BUYER = The company RECEIVING/PAYING this invoice (the customer/recipient)
  Example context: In a purchase invoice, BUYER is your company receiving the goods
  Fields: name, address, tax_id — whoever RECEIVES and PAYS the invoice

Use this EXACT structure:
{
  "invoice_number": "string or null",
  "invoice_date": "YYYY-MM-DD or null (use JSON null, not string)",
  "due_date": "YYYY-MM-DD or null (use JSON null, not string)",
  "currency": "string, default TND",
  "vendor": {
    "name": "company ISSUING the invoice (seller/supplier)",
    "address": "string or null",
    "tax_id": "string or null",
    "iban": "string or null"
  },
  "buyer": {
    "name": "company RECEIVING the invoice (customer/buyer)",
    "address": "string or null",
    "tax_id": "string or null"
  },
  "lines": [
    {
      "description": "product/service name from invoice line",
      "quantity": "COUNT of items (e.g. 10, 100.5) — MUST BE A NUMBER",
      "unit_price": "PRICE PER ITEM (e.g. 25.50) — MUST BE A NUMBER",
      "discount": "DISCOUNT PERCENT (0-100, e.g. 5 for 5%) — MUST BE A NUMBER",
      "tax_rate": "TAX PERCENT on this line (0-100, e.g. 19) — MUST BE A NUMBER",
      "line_total": "quantity × unit_price × (1 - discount/100) — MUST BE A NUMBER"
    }
  ],
  "totals": {
    "subtotal": "sum of all line_total values",
    "tax_amount": "sum of (line_total × tax_rate/100) for all lines",
    "discount": "total discount amount or 0",
    "total_due": "subtotal + tax_amount - discount"
  },
  "payment_terms": "string or null (e.g., 'Net 30', 'Due on receipt')",
  "notes": "string or null",
  "confidence_score": 0.95,
  "missing_fields": []
}

CRITICAL LINE ITEM FIELD RULES:
- Each line MUST have these 6 fields in the correct interpretation:
  * description: TEXT — item/service name
  * quantity: NUMBER — how many items
  * unit_price: NUMBER — price per single item
  * discount: NUMBER — discount percentage (0-100)
  * tax_rate: NUMBER — tax percentage (0-100)
  * line_total: NUMBER — final amount after discount

- Do NOT confuse quantity with unit_price
- Do NOT put discount value into unit_price field
- Do NOT put quantity value into discount field
- Verify: unit_price should typically be SMALLER than quantity (e.g., qty=100, price=3.0)
- Always calculate line_total = quantity × unit_price × (1 - discount/100)

CRITICAL OUTPUT RULES:
- NEVER add any comments (// or /* */) in the JSON output
- confidence_score: 0.0 to 1.0 — your honest assessment of extraction quality (be truthful)
- missing_fields: array of field paths you could not find
- All numeric fields MUST be actual numbers (not quoted strings): 1.5 not "1.5"
- All null values use JSON null, NEVER the string "null"
- lines must always be an array, even for single items
- NEVER truncate JSON — complete the entire object, close all braces
- Output ONLY the JSON object, nothing else. No markdown, code blocks, or wrapper text.
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
        raw_response = await self.llm.generate(messages, temperature=0.1)

        # Step 3 — Parse JSON safely with recovery
        try:
            # Strip accidental markdown fences if LLM adds them despite instructions
            clean = raw_response.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            
            clean = clean.strip()
            
            # Remove any lingering comments (// or /* */) that LLM might have added
            clean = _remove_json_comments(clean)
            
            # Try to parse JSON, recover from truncation if needed
            try:
                data = json.loads(clean)
            except json.JSONDecodeError:
                # If JSON is truncated, try to intelligently close it
                logger.warning("First JSON parse failed, attempting truncation recovery...")
                clean = _recover_truncated_json(clean)
                data = json.loads(clean)
            
            data = _fix_null_strings(data)
            
            # Validate and fix line item field assignments (detect swaps)
            data = _validate_and_fix_line_items(data)

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
def _remove_json_comments(text: str) -> str:
    """Remove // and /* */ style comments from JSON-like text."""
    import re
    # Remove // comments (but preserve colons and commas after values)
    text = re.sub(r'\s*//[^\n]*', '', text)
    # Remove /* */ comments
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    # Clean up any resulting double commas or trailing commas before closing braces
    text = re.sub(r',\s*([}\]])', r'\1', text)  # Remove trailing commas
    text = re.sub(r',,+', ',', text)  # Remove double commas
    return text.strip()


def _recover_truncated_json(text: str) -> str:
    """Try to recover from truncated JSON by intelligently closing structures."""
    import re
    text = text.strip()
    
    # Count braces and brackets
    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')
    
    # Close truncated arrays first (lines, totals, etc.)
    if open_brackets > 0:
        # Remove any incomplete last item before closing
        text = re.sub(r',\s*[{[]?[^,}\]]*$', '', text)
        text += ']' * open_brackets
    
    # Close truncated objects
    if open_braces > 0:
        # Clean up incomplete trailing comma/field
        text = re.sub(r'[,:]s*"[^"]*$', '', text)  # Remove incomplete quoted field
        text = re.sub(r',\s*$', '', text)  # Remove trailing comma
        text += '}' * open_braces
    
    return text


def _fix_null_strings(obj):
    """Recursively replace null-like string placeholders with None."""
    if isinstance(obj, dict):
        return {k: _fix_null_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_fix_null_strings(i) for i in obj]
    if isinstance(obj, str):
        value = obj.strip().lower()
        # Convert null-like strings to None
        if value in {"null", "none", "json null", "n/a", "na", ""}:
            return None
    return obj


def _validate_and_fix_line_items(data: dict) -> dict:
    """
    Detect and fix common line item field swap errors.
    E.g., if unit_price == discount value, swap them back.
    """
    if "lines" not in data or not data["lines"]:
        return data
    
    fixed_lines = []
    for idx, line in enumerate(data["lines"]):
        if not isinstance(line, dict):
            fixed_lines.append(line)
            continue
        
        qty = float(line.get("quantity") or 0)
        price = float(line.get("unit_price") or 0)
        discount = float(line.get("discount") or 0)
        tax = float(line.get("tax_rate") or 0)
        
        # Detect suspicious patterns (heuristics)
        warnings = []
        
        # If unit_price == quantity, they might be swapped
        if price > 0 and qty > 0 and abs(price - qty) < 1 and qty > 10:
            warnings.append(f"Suspicious: unit_price ({price}) ≈ quantity ({qty})")
        
        # If discount > 100 but unit_price looks reasonable percentage-ish
        if discount > 100 and price < 100:
            warnings.append(f"Suspicious: discount ({discount}) > 100%, unit_price ({price}) looks reasonable")
            # Likely swapped: discount and unit_price
            line["discount"], line["unit_price"] = line.get("unit_price"), line.get("discount")
            price, discount = line["unit_price"], line["discount"]
            warnings.append(f"→ Auto-swapped fields")
        
        # If unit_price is suspiciously small and discount is suspiciously large
        if price <= 5 and discount > 50 and qty > 10:
            # Could be swapped
            if line.get("discount") and line.get("unit_price"):
                test_total = qty * discount * (1 - price / 100)
                expected_total = float(line.get("line_total") or 0)
                if expected_total > 0 and abs(test_total - expected_total) < abs((qty * price * (1 - discount / 100)) - expected_total):
                    warnings.append(f"Probable swap: discount and unit_price")
                    line["discount"], line["unit_price"] = line.get("unit_price"), line.get("discount")
                    price, discount = line["unit_price"], line["discount"]
                    warnings.append(f"→ Auto-swapped fields")
        
        # Recalculate line_total to be safe
        final_qty = float(line.get("quantity") or 0)
        final_price = float(line.get("unit_price") or 0)
        final_discount = max(0, min(100, float(line.get("discount") or 0)))
        final_tax = float(line.get("tax_rate") or 0)
        calculated_total = round(final_qty * final_price * (1 - final_discount / 100), 2)
        line["line_total"] = calculated_total
        
        if warnings:
            logger.warning(f"Line {idx}: {' | '.join(warnings)}")
        
        fixed_lines.append(line)
    
    data["lines"] = fixed_lines
    return data
