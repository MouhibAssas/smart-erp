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

        def build_response(total: float, start_year: int, start_month: int, end_year: int, end_month: int, count: int) -> str:
            if start_year == end_year and start_month == end_month:
                return f"Revenue for {_month_label(end_year, end_month)} is {total:,.2f} TND"

            if start_year == end_year and start_month == 1 and end_month == 12:
                return f"Revenue for {end_year} is {total:,.2f} TND"

            return (
                f"Revenue for the last {count} months ({_short_month_label(start_year, start_month)} to "
                f"{_short_month_label(end_year, end_month)}) is {total:,.2f} TND"
            )

        async def _fetch_month_revenue(y: int, m: int) -> float:
            try:
                return float(await asyncio.to_thread(client.get_monthly_revenue, year=y, month=m))
            except Exception:
                return 0.0

        if months_back and months_back > 0:
            # Anchor the rolling window to the provided year/month when present.
            data: List[Dict[str, Any]] = []
            n = int(months_back)

            anchor_year = int(year) if year is not None else today.year
            anchor_month = int(month) if month is not None else today.month

            start_year = anchor_year
            start_month = anchor_month
            end_year = anchor_year
            end_month = anchor_month
            month_pairs: List[tuple[int, int]] = []
            for i in range(n - 1, -1, -1):
                m = anchor_month - i
                y = anchor_year
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

            async def _fetch_month_revenue_limited(y: int, m: int) -> float:
                async with semaphore:
                    return await _fetch_month_revenue(y, m)

            revenues = await asyncio.gather(
                *[_fetch_month_revenue_limited(y, m) for y, m in month_pairs]
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
                "response": build_response(round(total, 2), start_year, start_month, end_year, end_month, n),
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

        # Explicit period selection when no rolling window is requested.
        if year is not None and month is not None:
            y = int(year)
            m = int(month)
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

        # Year-only request: sum all months in the requested year.
        if year is not None and month is None:
            y = int(year)
            month_pairs = [(y, m) for m in range(1, 13)]
            data: List[Dict[str, Any]] = []
            semaphore = asyncio.Semaphore(4)

            async def _fetch_year_month_revenue(y_val: int, m_val: int) -> float:
                async with semaphore:
                    return await _fetch_month_revenue(y_val, m_val)

            revenues = await asyncio.gather(
                *[_fetch_year_month_revenue(y, m) for y, m in month_pairs]
            )

            for (y_val, m_val), revenue in zip(month_pairs, revenues):
                label = _short_month_label(y_val, m_val)
                data.append({
                    "month": label,
                    "year": y_val,
                    "month_num": m_val,
                    "revenue": round(revenue, 2),
                })

            total = sum(d["revenue"] for d in data)
            await ctx.info(
                f"Computed revenue for year {y} | total={round(total, 2)}"
            )
            return {
                "ok": True,
                "response": build_response(round(total, 2), y, 1, y, 12, 12),
                "message": f"Revenue for {y}",
                "data": data,
                "total": round(total, 2),
                "meta": {
                    "start_year": y,
                    "start_month": 1,
                    "end_year": y,
                    "end_month": 12,
                },
            }

        if year is None and month is None:
            return {
                "ok": False,
                "error": "Provide a year, a month with year, or months_back.",
            }

        return {
            "ok": False,
            "error": "Provide both year and month for a single-month revenue query.",
        }

    except OdooClientError as exc:
        await ctx.warning(f"Odoo error: {exc}")
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        await ctx.warning(f"Unexpected error: {exc}")
        return {"ok": False, "error": f"Unexpected error: {exc}"}