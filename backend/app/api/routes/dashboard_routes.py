import logging
import asyncio
from typing import Any, Dict, List

from fastapi import APIRouter, Query, Request, Depends
from app.middleware.dependencies import require_roles
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_roles("operator", "admin"))])
logger = logging.getLogger(__name__)


def _to_float(value: Any) -> float:
	try:
		return float(value)
	except (TypeError, ValueError):
		return 0.0


def _tool_error(result: Any, fallback: str) -> str:
	if isinstance(result, dict):
		return str(result.get("error") or fallback)
	return fallback


@router.get("/kpis")
async def get_dashboard_kpis(
	request: Request,
	list_limit: int = Query(8, ge=1, le=25, description="How many recent unpaid invoices to keep per type."),
):
	"""Dashboard KPI endpoint that aggregates unpaid stats and current month revenue."""
	agent = request.app.state.agent

	customer_task = agent._call_tool(
		"get_unpaid_invoices",
		{"invoice_type": "customer", "limit": list_limit},
	)
	vendor_task = agent._call_tool(
		"get_unpaid_invoices",
		{"invoice_type": "vendor", "limit": list_limit},
	)
	revenue_task = agent._call_tool("get_revenue", {})

	customer_result, vendor_result, revenue_result = await asyncio.gather(
		customer_task,
		vendor_task,
		revenue_task,
		return_exceptions=True,
	)

	if isinstance(customer_result, Exception):
		logger.exception("Customer unpaid invoices tool call failed", exc_info=customer_result)
		return {"ok": False, "error": "Failed to fetch customer unpaid invoices."}
	if not isinstance(customer_result, dict) or not customer_result.get("ok"):
		return {"ok": False, "error": _tool_error(customer_result, "Failed to fetch customer unpaid invoices.")}

	if isinstance(vendor_result, Exception):
		logger.exception("Vendor unpaid invoices tool call failed", exc_info=vendor_result)
		return {"ok": False, "error": "Failed to fetch vendor unpaid invoices."}
	if not isinstance(vendor_result, dict) or not vendor_result.get("ok"):
		return {"ok": False, "error": _tool_error(vendor_result, "Failed to fetch vendor unpaid invoices.")}

	if isinstance(revenue_result, Exception):
		logger.exception("Revenue tool call failed", exc_info=revenue_result)
		return {"ok": False, "error": "Failed to fetch revenue data."}
	if not isinstance(revenue_result, dict) or not revenue_result.get("ok"):
		return {"ok": False, "error": _tool_error(revenue_result, "Failed to fetch revenue data.")}

	customer_summary = customer_result.get("summary") or {}
	vendor_summary = vendor_result.get("summary") or {}
	revenue_data = revenue_result.get("data") or []
	month_label = revenue_data[0].get("month") if revenue_data and isinstance(revenue_data[0], dict) else "This month"

	return {
		"ok": True,
		"kpis": {
			"unpaid_customer_invoices": int(customer_summary.get("count") or 0),
			"unpaid_customer_residual": round(_to_float(customer_summary.get("total_residual")), 2),
			"unpaid_vendor_bills": int(vendor_summary.get("count") or 0),
			"unpaid_vendor_residual": round(_to_float(vendor_summary.get("total_residual")), 2),
			"monthly_revenue": round(_to_float(revenue_result.get("total")), 2),
			"month": month_label,
		},
		"unpaid_customer_list": customer_result.get("invoices") or [],
		"unpaid_vendor_list": vendor_result.get("invoices") or [],
	}


@router.get("/invoices/recent")
async def get_recent_unpaid_invoices(
	request: Request,
	limit: int = Query(8, ge=1, le=50),
	invoice_type: str = Query("both", description="customer, vendor, or both"),
):
	"""Recent unpaid invoices for dashboard list widgets."""
	normalized_type = (invoice_type or "both").strip().lower()
	if normalized_type not in {"customer", "vendor", "both"}:
		return {"ok": False, "error": "invoice_type must be one of: customer, vendor, both."}

	result = await request.app.state.agent._call_tool(
		"get_unpaid_invoices",
		{"invoice_type": normalized_type, "limit": limit},
	)
	if not isinstance(result, dict) or not result.get("ok"):
		return {"ok": False, "error": _tool_error(result, "Failed to fetch recent unpaid invoices.")}

	invoices: List[Dict[str, Any]] = result.get("invoices") or []
	invoices_sorted = sorted(
		invoices,
		key=lambda inv: (str(inv.get("invoice_date") or ""), int(inv.get("id") or 0)),
		reverse=True,
	)

	return {
		"ok": True,
		"invoice_type": normalized_type,
		"count": len(invoices_sorted),
		"invoices": invoices_sorted[:limit],
	}


@router.get("/revenue/monthly")
async def get_monthly_revenue(
	request: Request,
	months: int = Query(6, ge=1, le=36, description="How many months back to return."),
	current_user: User = Depends(require_roles("admin", "operator")),
):
	"""Monthly revenue timeseries used by dashboard charts."""
	result = await request.app.state.agent._call_tool(
		"get_revenue",
		{"months_back": months},
	)

	if not isinstance(result, dict) or not result.get("ok"):
		return {"ok": False, "error": _tool_error(result, "Failed to fetch monthly revenue.")}

	return {
		"ok": True,
		"message": result.get("message"),
		"response": result.get("response"),
		"data": result.get("data") or [],
		"total": round(_to_float(result.get("total")), 2),
		"meta": result.get("meta") or {},
	}
