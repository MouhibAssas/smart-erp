import asyncio
from typing import Annotated, Any, Dict, Union

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


async def _resolve_id(
    client: OdooSessionClient,
    ctx: Context,
    value: Union[int, str, None],
    field_name: str,
    odoo_model: str,
) -> Union[int, None]:
    """
    Helper to resolve a field value to an Odoo record ID.
    If value is int, return it. If string, search for it by name and return the ID.
    """
    if not value:
        return None
    
    if isinstance(value, int):
        return value
    
    if isinstance(value, str):
        name = str(value).strip()
        if not name or name.lower() == "null":
            return None
        
        try:
            if odoo_model == "hr.department":
                matches = await asyncio.to_thread(
                    client.search_departments,
                    filters={"domain": [["name", "ilike", name]]},
                    limit=1,
                )
            elif odoo_model == "res.company":
                matches = await asyncio.to_thread(
                    client.search_companies,
                    filters={"domain": [["name", "ilike", name]]},
                    limit=1,
                )
            elif odoo_model == "hr.work.location":
                matches = await asyncio.to_thread(
                    client.search_work_locations,
                    filters={"domain": [["name", "ilike", name]]},
                    limit=1,
                )
            else:
                return None
            
            if matches:
                return matches[0]["id"]
            else:
                await ctx.warning(f"No {odoo_model} found with name '{name}'")
                return None
        except Exception as exc:
            await ctx.warning(f"Error searching for {odoo_model}: {exc}")
            return None
    
    return None


def _parse_optional_int(value: Union[int, str, None], field_name: str) -> tuple[Union[int, None], Union[str, None]]:
    """Parse optional integer-like input, accepting empty strings as None."""
    if value is None:
        return None, None
    if isinstance(value, int):
        return value, None
    text = str(value).strip()
    if not text or text.lower() == "null":
        return None, None
    try:
        return int(text), None
    except (TypeError, ValueError):
        return None, f"{field_name} must be an integer"


async def create_employee(
    name: Annotated[str, Field(description="Employee name, e.g. 'John Doe'.")],
    work_email: Annotated[str | None, Field(description="Optional work email address.")] = None,
    email: Annotated[str | None, Field(description="Alias for work email address.")] = None,
    mobile_phone: Annotated[str | int | None, Field(description="Optional mobile phone number.")] = None,
    phone: Annotated[str | int | None, Field(description="Optional phone number.")] = None,
    work_phone: Annotated[str | int | None, Field(description="Alias for phone number.")] = None,
    phone_number: Annotated[str | int | None, Field(description="Alias for phone number.")] = None,
    number_phone: Annotated[str | int | None, Field(description="Alias for phone number.")] = None,
    department_id: Annotated[int | str | None, Field(description="Optional department ID (int) or name (str).")] = None,
    department_name: Annotated[str | None, Field(description="Alias for department name.")] = None,
    job_id: Annotated[int | str | None, Field(description="Optional job position ID (int) or name (str).")] = None,
    job_name: Annotated[str | None, Field(description="Alias for job name.")] = None,
    company_id: Annotated[int | str | None, Field(description="Optional company ID (int) or name (str).")] = None,
    work_location_id: Annotated[int | str | None, Field(description="Optional work location ID (int) or name (str).")] = None,
    resource_calendar_id: Annotated[int | str | None, Field(description="Optional calendar/schedule ID.")] = None,
    country_id: Annotated[int | str | None, Field(description="Optional country ID.")] = None,
    marital: Annotated[str | None, Field(description="Optional marital status.")] = None,
    birthday: Annotated[str | None, Field(description="Optional birthday in YYYY-MM-DD format.")] = None,
    identification_id: Annotated[str | None, Field(description="Optional identification number (e.g. ID card).")] = None,
    ctx: Context = None,
) -> Dict[str, Any]:
    """Create a new Odoo employee."""

    if not isinstance(name, str) or not name.strip():
        return {"ok": False, "error": "name is required and must be a non-empty string."}

    try:
        client = _get_client(ctx)
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}

    try:
        await ctx.info(f"Creating employee: {name.strip()}")

        vals: Dict[str, Any] = {
            "name": name.strip(),
        }

        effective_work_email = work_email if work_email not in (None, "") else email
        effective_department_identifier = (
            department_id if department_id not in (None, "") else department_name
        )
        effective_job_identifier = job_id if job_id not in (None, "") else job_name
        effective_phone = phone
        if effective_phone in (None, ""):
            effective_phone = work_phone
        if effective_phone in (None, ""):
            effective_phone = phone_number
        if effective_phone in (None, ""):
            effective_phone = number_phone

        optional_fields = {
            "work_email": effective_work_email,
            "mobile_phone": mobile_phone,
            "phone": effective_phone,
            "marital": marital,
            "birthday": birthday,
            "identification_id": identification_id,
        }
        
        for field_name, value in optional_fields.items():
            if value and str(value).strip() and str(value).strip().lower() != "null":
                vals[field_name] = str(value).strip()

        # Resolve related fields that can be passed as strings or ints
        resolved_department = await _resolve_id(
            client, ctx, effective_department_identifier, "department_id", "hr.department"
        )
        if resolved_department:
            vals["department_id"] = resolved_department

        # Do not search hr.job: keep provided job value as-is.
        # If numeric, use job_id. If text, write to job_title.
        parsed_job_id, job_error = _parse_optional_int(
            effective_job_identifier, "job_id"
        )
        if job_error and effective_job_identifier not in (None, ""):
            job_text = str(effective_job_identifier).strip()
            if job_text and job_text.lower() != "null":
                vals["job_title"] = job_text
        elif parsed_job_id is not None:
            vals["job_id"] = parsed_job_id

        resolved_company = await _resolve_id(
            client, ctx, company_id, "company_id", "res.company"
        )
        if resolved_company:
            vals["company_id"] = resolved_company

        resolved_location = await _resolve_id(
            client, ctx, work_location_id, "work_location_id", "hr.work.location"
        )
        if resolved_location:
            vals["work_location_id"] = resolved_location

        # Handle optional integer fields
        parsed_calendar_id, calendar_error = _parse_optional_int(
            resource_calendar_id, "resource_calendar_id"
        )
        if calendar_error:
            return {"ok": False, "error": calendar_error}
        if parsed_calendar_id is not None:
            vals["resource_calendar_id"] = parsed_calendar_id

        parsed_country_id, country_error = _parse_optional_int(
            country_id, "country_id"
        )
        if country_error:
            return {"ok": False, "error": country_error}
        if parsed_country_id is not None:
            vals["country_id"] = parsed_country_id

        employee_id = await asyncio.to_thread(client.create_employee, vals=vals)
        employee = await asyncio.to_thread(client.read_employee, record_id=employee_id)
        await ctx.info(f"Employee created: id={employee_id} name={employee.get('name')}")

        return {
            "ok": True,
            "response": f"Employee created successfully: {employee.get('name')}",
            "employee": employee,
            "summary": {
                "id": employee.get("id"),
                "name": employee.get("name"),
                "work_email": employee.get("work_email"),
                "mobile_phone": employee.get("mobile_phone"),
                "department_id": employee.get("department_id"),
                "job_id": employee.get("job_id"),
                "company_id": employee.get("company_id"),
            },
        }
    except OdooClientError as exc:
        await ctx.warning(f"Odoo error: {exc}")
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        await ctx.warning(f"Unexpected error: {exc}")
        return {"ok": False, "error": f"Unexpected error: {exc}"}

