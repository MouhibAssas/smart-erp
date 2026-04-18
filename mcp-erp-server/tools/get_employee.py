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
    ctx: Context = None,
) -> Dict[str, Any]:
    """Get an Odoo employee by ID, name, email, job title, or department."""

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

    try:
        client = _get_client(ctx)
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}

    try:
        if has_id:
            await ctx.info(f"Reading employee id={employee_id}")
            employee = client.read_employee(record_id=employee_id)
        elif has_name:
            name = str(employee_name).strip()
            await ctx.info(f"Searching employee by name: {name}")
            matches = client.search_employees(
                filters={"domain": [["name", "ilike", name]]},
                limit=1,
            )
            if not matches:
                return {
                    "ok": False,
                    "error": f"No employee found with name '{name}'.",
                }
            employee = matches[0]
        elif has_email:
            email = str(work_email).strip()
            await ctx.info(f"Searching employee by work email: {email}")
            matches = client.search_employees(
                filters={"domain": [["work_email", "ilike", email]]},
                limit=1,
            )
            if not matches:
                return {
                    "ok": False,
                    "error": f"No employee found with work email '{email}'.",
                }
            employee = matches[0]
        elif has_job:
            job = str(job_name).strip()
            await ctx.info(f"Searching job by name: {job}")
            job_matches = client.search_jobs(
                filters={"domain": [["name", "ilike", job]]},
                limit=1,
            )
            if not job_matches:
                return {
                    "ok": False,
                    "error": f"No job found with name '{job}'.",
                }
            job_id = job_matches[0]["id"]
            await ctx.info(f"Searching employees with job_id={job_id}")
            matches = client.search_employees(
                filters={"domain": [["job_id", "=", job_id]]},
                limit=1,
            )
            if not matches:
                return {
                    "ok": False,
                    "error": f"No employee found with job '{job}'.",
                }
            employee = matches[0]
        else:  # has_dept
            dept = str(department_name).strip()
            await ctx.info(f"Searching department by name: {dept}")
            dept_matches = client.search_departments(
                filters={"domain": [["name", "ilike", dept]]},
                limit=1,
            )
            if not dept_matches:
                return {
                    "ok": False,
                    "error": f"No department found with name '{dept}'.",
                }
            dept_id = dept_matches[0]["id"]
            await ctx.info(f"Searching employees with department_id={dept_id}")
            matches = client.search_employees(
                filters={"domain": [["department_id", "=", dept_id]]},
                limit=1,
            )
            if not matches:
                return {
                    "ok": False,
                    "error": f"No employee found in department '{dept}'.",
                }
            employee = matches[0]

        await ctx.info(f"Employee fetched — id {employee.get('id')}")

        return {
            "ok": True,
            "message": "Employee data fetched successfully",
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
            "employee": employee,
            "data": employee,
        }
    except OdooClientError as exc:
        await ctx.warning(f"Odoo error: {exc}")
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        await ctx.warning(f"Unexpected error: {exc}")
        return {"ok": False, "error": f"Unexpected error: {exc}"}

