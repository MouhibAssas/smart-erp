from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional


ToolHandler = Callable[..., Awaitable[Dict[str, Any]]]


@dataclass(frozen=True)
class ToolDefinition:
	name: str
	description: str
	usage: str
	handler: ToolHandler


class ToolRegistry:
	def __init__(self) -> None:
		self._tools: Dict[str, ToolDefinition] = {}
		self._invoices: Dict[str, Dict[str, Any]] = {}
		self._seed_sample_data()
		self._register_default_tools()

	def register(self, definition: ToolDefinition) -> None:
		self._tools[definition.name] = definition

	def get(self, tool_name: str) -> ToolHandler:
		definition = self._tools.get(tool_name)
		if not definition:
			available = ", ".join(sorted(self._tools.keys()))
			raise KeyError(f"Unknown tool '{tool_name}'. Available tools: {available}")
		return definition.handler

	def list_tools(self) -> str:
		lines: List[str] = []
		for definition in sorted(self._tools.values(), key=lambda t: t.name):
			lines.append(f"- {definition.name}: {definition.description}. Usage: {definition.usage}")
		return "\n".join(lines)

	def _register_default_tools(self) -> None:
		self.register(
			ToolDefinition(
				name="get_invoice",
				description="Read invoice details by ID, or list latest invoices when no ID is provided",
				usage="User asks to find, show, check or review an invoice",
				handler=self._get_invoice,
			)
		)
		self.register(
			ToolDefinition(
				name="create_invoice",
				description="Create a new invoice draft from message text or uploaded file metadata",
				usage="User asks to create/add/new invoice or uploads an invoice file",
				handler=self._create_invoice,
			)
		)
		self.register(
			ToolDefinition(
				name="update_invoice",
				description="Update invoice status or amount for an existing invoice",
				usage="User asks to modify/update/approve/cancel an invoice",
				handler=self._update_invoice,
			)
		)

	def _seed_sample_data(self) -> None:
		now = datetime.utcnow().isoformat()
		self._invoices = {
			"INV-1001": {
				"id": "INV-1001",
				"vendor": "Atlas Supplies",
				"amount": 1299.99,
				"currency": "EUR",
				"status": "draft",
				"source": "seed",
				"created_at": now,
				"updated_at": now,
			},
			"INV-1002": {
				"id": "INV-1002",
				"vendor": "Nordic Industrial",
				"amount": 420.50,
				"currency": "EUR",
				"status": "approved",
				"source": "seed",
				"created_at": now,
				"updated_at": now,
			},
		}

	async def _get_invoice(self, user_message: str = "", **_: Any) -> Dict[str, Any]:
		invoice_id = self._extract_invoice_id(user_message)

		if invoice_id:
			invoice = self._invoices.get(invoice_id)
			if not invoice:
				return {
					"tool": "get_invoice",
					"ok": False,
					"error": f"Invoice '{invoice_id}' not found",
					"available_ids": sorted(self._invoices.keys()),
				}
			return {
				"tool": "get_invoice",
				"ok": True,
				"invoice": invoice,
			}

		# No ID provided: return a lightweight list so the assistant can guide the user.
		invoices = [
			{
				"id": item["id"],
				"vendor": item["vendor"],
				"amount": item["amount"],
				"currency": item["currency"],
				"status": item["status"],
			}
			for item in sorted(self._invoices.values(), key=lambda inv: inv["id"])
		]
		return {
			"tool": "get_invoice",
			"ok": True,
			"count": len(invoices),
			"invoices": invoices,
		}

	async def _create_invoice(
		self,
		user_message: str = "",
		file_bytes: Optional[bytes] = None,
		filename: Optional[str] = None,
		**_: Any,
	) -> Dict[str, Any]:
		invoice_id = self._next_invoice_id()
		amount = self._extract_amount(user_message) or 0.0
		now = datetime.utcnow().isoformat()

		invoice = {
			"id": invoice_id,
			"vendor": self._extract_vendor(user_message),
			"amount": amount,
			"currency": "EUR",
			"status": "draft",
			"source": "upload" if file_bytes else "chat",
			"filename": filename if filename else None,
			"notes": user_message.strip() if user_message else "",
			"created_at": now,
			"updated_at": now,
		}
		self._invoices[invoice_id] = invoice

		return {
			"tool": "create_invoice",
			"ok": True,
			"message": f"Invoice {invoice_id} created",
			"invoice": invoice,
		}

	async def _update_invoice(self, user_message: str = "", **_: Any) -> Dict[str, Any]:
		invoice_id = self._extract_invoice_id(user_message)
		if not invoice_id:
			return {
				"tool": "update_invoice",
				"ok": False,
				"error": "No invoice ID found in message (expected format: INV-XXXX)",
			}

		invoice = self._invoices.get(invoice_id)
		if not invoice:
			return {
				"tool": "update_invoice",
				"ok": False,
				"error": f"Invoice '{invoice_id}' not found",
				"available_ids": sorted(self._invoices.keys()),
			}

		status = self._extract_status(user_message)
		if status:
			invoice["status"] = status

		amount = self._extract_amount(user_message)
		if amount is not None:
			invoice["amount"] = amount

		invoice["updated_at"] = datetime.utcnow().isoformat()
		self._invoices[invoice_id] = invoice

		return {
			"tool": "update_invoice",
			"ok": True,
			"message": f"Invoice {invoice_id} updated",
			"invoice": invoice,
		}

	def _next_invoice_id(self) -> str:
		if not self._invoices:
			return "INV-1001"

		nums = []
		for inv_id in self._invoices:
			match = re.search(r"(\d+)$", inv_id)
			if match:
				nums.append(int(match.group(1)))
		next_num = (max(nums) + 1) if nums else 1001
		return f"INV-{next_num}"

	@staticmethod
	def _extract_invoice_id(text: str) -> Optional[str]:
		match = re.search(r"\bINV[-_ ]?(\d{3,})\b", text.upper())
		if not match:
			return None
		return f"INV-{match.group(1)}"

	@staticmethod
	def _extract_amount(text: str) -> Optional[float]:
		# Supports patterns like: 1200, 1200.50, 1,200.50, amount 350
		match = re.search(r"(?:amount\s*[:=]?\s*)?(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
		if not match:
			return None
		value = match.group(1).replace(",", "")
		try:
			return float(value)
		except ValueError:
			return None

	@staticmethod
	def _extract_vendor(text: str) -> str:
		# Best-effort vendor extraction from "vendor: X" / "from X" phrasing.
		vendor_match = re.search(r"vendor\s*[:=]\s*([A-Za-z0-9 &._-]{2,})", text, flags=re.IGNORECASE)
		if vendor_match:
			return vendor_match.group(1).strip()

		from_match = re.search(r"from\s+([A-Za-z0-9 &._-]{2,})", text, flags=re.IGNORECASE)
		if from_match:
			return from_match.group(1).strip()

		return "Unknown Vendor"

	@staticmethod
	def _extract_status(text: str) -> Optional[str]:
		lowered = text.lower()
		if "approve" in lowered or "approved" in lowered:
			return "approved"
		if "cancel" in lowered or "canceled" in lowered or "cancelled" in lowered:
			return "cancelled"
		if "paid" in lowered:
			return "paid"
		if "draft" in lowered:
			return "draft"
		return None


tool_registry = ToolRegistry()
