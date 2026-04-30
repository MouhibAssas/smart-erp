from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan  
from clients.odoo_client import OdooSessionClient , OdooClientError
from dotenv import load_dotenv
import asyncio
import logging


load_dotenv()
logger = logging.getLogger(__name__)

@lifespan
async def app_lifespan(server):
    odoo = None
    try:
        # Build the Odoo client in lifespan without crashing MCP startup.
        odoo = OdooSessionClient()

        # Odoo auth uses blocking urllib; run it in a worker thread so stdio
        # handshake and MCP startup are not blocked on the event loop.
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, odoo.authenticate)
        logger.info("Odoo connection verified successfully")
    except OdooClientError as exc:
        logger.warning("Odoo connection check failed at startup: %s", exc)
    except Exception as exc:
        logger.exception("Unexpected startup error while preparing Odoo client: %s", exc)
    try:
        yield {"odoo": odoo}
    finally:
        pass

mcp = FastMCP("McpErpServer", lifespan=app_lifespan)

from tools.create_invoice import create_invoice
from tools.get_invoice import get_invoice
from tools.create_partner import create_partner
from tools.get_partner import get_partner
from tools.create_employee import create_employee
from tools.get_employee import get_employee
from tools.get_unpaid_invoices import get_unpaid_invoices
from tools.search_invoices_advanced import search_invoices_advanced
from tools.get_revenue import get_revenue
# from tools.update_invoice import update_invoice

mcp.add_tool(create_invoice)
mcp.add_tool(get_invoice)
mcp.add_tool(create_partner)
mcp.add_tool(get_partner)
mcp.add_tool(create_employee)
mcp.add_tool(get_employee)
mcp.add_tool(get_unpaid_invoices)
mcp.add_tool(search_invoices_advanced)
mcp.add_tool(get_revenue)
# mcp.add_tool(update_invoice)

if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)