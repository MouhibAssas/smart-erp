import asyncio
from typing import Annotated, Any, Dict, List
from fastmcp import Context
from pydantic import Field
from clients.odoo_client import OdooClientError, OdooSessionClient
from datetime import date


def _month_label(year: int, month: int) -> str:
    return date(year, month, 1).strftime("%B %Y")


def _short_month_label(year: int, month: int) -> str:
    return date(year, month, 1).strftime("%b %Y")


def _get_client(ctx: Context) -> OdooSessionClient:
    client = (ctx.lifespan_context or {}).get("odoo")
    if not isinstance(client, OdooSessionClient):
        raise RuntimeError("Odoo client not found in lifespan context.")
    return client


async def get_revenue(
    year: Annotated[int, Field(description="Year, e.g. 2025")] = None,
    month: Annotated[int, Field(description="Month 1-12, e.g. 4 for April")] = None,
    months_back: Annotated[int, Field(description="How many past months to return (1-12). Overrides year/month.")] = None,
    ctx: Context = None,
) -> Dict[str, Any]:
    """
    Get monthly revenue (sum of posted customer invoices) for Odoo.
    Use months_back to get a range of recent months, or year+month for a specific month.
    """
    try:
        client = _get_client(ctx)
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}

    try:
        await ctx.info(
            f"get_revenue: year={year} month={month} months_back={months_back}"
        )
        today = date.today()

        def build_response(total: float, start_year: int, start_month: int, end_year: int, end_month: int) -> str:
            if start_year == end_year and start_month == end_month:
                return f"Revenue for {_month_label(end_year, end_month)} is {total:,.2f} TND"

            return (
                f"Revenue for the last {n} months ({_short_month_label(start_year, start_month)} to "
                f"{_short_month_label(end_year, end_month)}) is {total:,.2f} TND"
            )

        if months_back and months_back > 0:
            # Return a range of months
            data: List[Dict[str, Any]] = []
            # n = min(int(months_back), 12) # no 1 year limit at the moment !
            n = int(months_back)

            start_year = today.year
            start_month = today.month
            end_year = today.year
            end_month = today.month
            month_pairs: List[tuple[int, int]] = []
            for i in range(n - 1, -1, -1):
                m = today.month - i
                y = today.year
                while m <= 0:
                    m += 12
                    y -= 1
                if i == n - 1:
                    start_year = y
                    start_month = m
                if i == 0:
                    end_year = y
                    end_month = m
                month_pairs.append((y, m))

            semaphore = asyncio.Semaphore(4)

            async def _fetch_month_revenue(y: int, m: int) -> float:
                async with semaphore:
                    try:
                        return float(await asyncio.to_thread(client.get_monthly_revenue, year=y, month=m))
                    except Exception:
                        return 0.0

            revenues = await asyncio.gather(
                *[_fetch_month_revenue(y, m) for y, m in month_pairs]
            )

            for (y, m), revenue in zip(month_pairs, revenues):
                label = _short_month_label(y, m)
                data.append({
                    "month": label,
                    "year": y,
                    "month_num": m,
                    "revenue": round(revenue, 2),
                })
            total = sum(d["revenue"] for d in data)
            await ctx.info(
                f"Computed revenue for {n} months | total={round(total, 2)}"
            )
            return {
                "ok": True,
                "response": build_response(round(total, 2), start_year, start_month, end_year, end_month),
                "message": f"Revenue for last {n} months",
                "data": data,
                "total": round(total, 2),
                "meta": {
                    "start_year": start_year,
                    "start_month": start_month,
                    "end_year": end_year,
                    "end_month": end_month,
                },
            }

        # Single month
        y = int(year) if year else today.year
        m = int(month) if month else today.month
        revenue = await asyncio.to_thread(client.get_monthly_revenue, year=y, month=m)
        label = _month_label(y, m)
        await ctx.info(
            f"Computed revenue for {label} | total={round(revenue, 2)}"
        )
        return {
            "ok": True,
            "response": f"Revenue for {label} is {round(revenue, 2):,.2f} TND",
            "message": f"Revenue for {label}",
            "data": [{"month": label, "year": y, "month_num": m, "revenue": round(revenue, 2)}],
            "total": round(revenue, 2),
            "meta": {
                "start_year": y,
                "start_month": m,
                "end_year": y,
                "end_month": m,
            },
        }

    except OdooClientError as exc:
        await ctx.warning(f"Odoo error: {exc}")
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        await ctx.warning(f"Unexpected error: {exc}")
        return {"ok": False, "error": f"Unexpected error: {exc}"}