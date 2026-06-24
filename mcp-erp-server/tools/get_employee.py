import asyncio
from typing import Annotated, Any, Dict

from fastmcp import Context
from pydantic import Field

from clients.odoo_client import OdooClientError, OdooSessionClient


def _get_client(ctx: Context) -> OdooSessionClient:
    client = (ctx.lifespan_context or {}).get("odoo")
    if not isinstance(client, OdooSessionClient):
        raise RuntimeError(
            "Odoo client not found in lifespan context. "
            "Is the MCP server running correctly?"
        )
    return client


async def get_employee(
    employee_id: Annotated[int | None, Field(description="Odoo employee ID.")] = None,
    employee_name: Annotated[
        str | None,
        Field(description="Employee name to search case-insensitively (first match)."),
    ] = None,
    work_email: Annotated[
        str | None,
        Field(description="Employee work email to search case-insensitively."),
    ] = None,
    job_name: Annotated[
        str | None,
        Field(description="Job title name to search for employees with that job."),
    ] = None,
    department_name: Annotated[
        str | None,
        Field(description="Department name to search for employees in that department."),
    ] = None,
    max_results: Annotated[
        int,
        Field(description="Maximum number of employee matches to return when searching by name."),
    ] = 10,
    ctx: Context = None,
) -> Dict[str, Any]:
    """Get an Odoo employee by ID, name, email, job title, or department."""

    def _format_employee_line(employee: Dict[str, Any]) -> str:
        parts = [f"ID: {employee.get('id')}", f"Name: {employee.get('name') or '-'}"]
        if employee.get("work_email"):
            parts.append(f"Email: {employee.get('work_email')}")
        if employee.get("mobile_phone"):
            parts.append(f"Mobile: {employee.get('mobile_phone')}")
        return " | ".join(parts)

    has_id = employee_id is not None
    has_name = bool(employee_name and str(employee_name).strip())
    has_email = bool(work_email and str(work_email).strip())
    has_job = bool(job_name and str(job_name).strip())
    has_dept = bool(department_name and str(department_name).strip())

    if not (has_id or has_name or has_email or has_job or has_dept):
        return {
            "ok": False,
            "error": "Provide either employee_id, employee_name, work_email, job_name, or department_name.",
        }

    if max_results <= 0:
        return {"ok": False, "error": "max_results must be greater than 0."}

    try:
        client = _get_client(ctx)
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}

    try:
        if has_id:
            await ctx.info(f"Reading employee id={employee_id}")
            employee = await asyncio.to_thread(client.read_employee, record_id=employee_id)
            employees = [employee]
        elif has_name:
            name = str(employee_name).strip()
            await ctx.info(f"Searching employee by name: {name}")
            employees = await asyncio.to_thread(
                client.search_employees,
                filters={"domain": [["name", "ilike", name]]},
                limit=max_results,
            )
            if not employees:
                return {
                    "ok": False,
                    "error": f"No employee found with name '{name}'.",
                }
        elif has_email:
            email = str(work_email).strip()
            await ctx.info(f"Searching employee by work email: {email}")
            employees = await asyncio.to_thread(
                client.search_employees,
                filters={"domain": [["work_email", "ilike", email]]},
                limit=max_results,
            )
            if not employees:
                return {
                    "ok": False,
                    "error": f"No employee found with work email '{email}'.",
                }
        elif has_job:
            job = str(job_name).strip()
            await ctx.info(f"Searching job by name: {job}")
            job_matches = await asyncio.to_thread(
                client.search_jobs,
                filters={"domain": [["name", "ilike", job]]},
                limit=max_results,
            )
            if not job_matches:
                return {
                    "ok": False,
                    "error": f"No job found with name '{job}'.",
                }
            job_id = job_matches[0]["id"]
            await ctx.info(f"Searching employees with job_id={job_id}")
            employees = await asyncio.to_thread(
                client.search_employees,
                filters={"domain": [["job_id", "=", job_id]]},
                limit=max_results,
            )
            if not employees:
                return {
                    "ok": False,
                    "error": f"No employee found with job '{job}'.",
                }
        else:  # has_dept
            dept = str(department_name).strip()
            await ctx.info(f"Searching department by name: {dept}")
            dept_matches = await asyncio.to_thread(
                client.search_departments,
                filters={"domain": [["name", "ilike", dept]]},
                limit=max_results,
            )
            if not dept_matches:
                return {
                    "ok": False,
                    "error": f"No department found with name '{dept}'.",
                }
            dept_id = dept_matches[0]["id"]
            await ctx.info(f"Searching employees with department_id={dept_id}")
            employees = await asyncio.to_thread(
                client.search_employees,
                filters={"domain": [["department_id", "=", dept_id]]},
                limit=max_results,
            )
            if not employees:
                return {
                    "ok": False,
                    "error": f"No employee found in department '{dept}'.",
                }

        if has_name or has_email or has_job or has_dept:
            employee_ids = [e.get("id") for e in employees]
            await ctx.info(f"Found {len(employees)} employee(s) with IDs: {employee_ids}")
            if has_name:
                query_label = f"'{name}'"
            elif has_email:
                query_label = f"work email '{email}'"
            elif has_job:
                query_label = f"job '{job}'"
            else:
                query_label = f"department '{dept}'"
            response_lines = [f"Found {len(employees)} employee(s) matching {query_label}:"]
            for item in employees:
                response_lines.append(f"- {_format_employee_line(item)}")
            response_text = "\n".join(response_lines)
        else:
            employee = employees[0]
            await ctx.info(f"Employee fetched — id {employee.get('id')}")
            response_text = f"Employee found: {_format_employee_line(employee)}"

        employee = employees[0]

        return {
            "ok": True,
            "message": "Employee data fetched successfully",
            "response": response_text,
            "summary": {
                "id": employee.get("id"),
                "name": employee.get("name"),
                "work_email": employee.get("work_email"),
                "mobile_phone": employee.get("mobile_phone"),
                "department_id": employee.get("department_id"),
                "job_id": employee.get("job_id"),
                "company_id": employee.get("company_id"),
                "marital": employee.get("marital"),
            },
            "count": len(employees),
            "employees": employees,
            "employee": employee,
            "data": employee,
        }
    except OdooClientError as exc:
        await ctx.warning(f"Odoo error: {exc}")
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        await ctx.warning(f"Unexpected error: {exc}")
        return {"ok": False, "error": f"Unexpected error: {exc}"}

