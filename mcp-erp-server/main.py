from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan  
from clients.odoo_client import OdooSessionClient , OdooClientError
from dotenv import load_dotenv
import logging


load_dotenv()
logger = logging.getLogger(__name__)

@lifespan
async def app_lifespan(server):
    odoo = OdooSessionClient()
    try:
        odoo.authenticate()
        logger.info("Odoo connection verified successfully")
    except OdooClientError as exc:
        logger.warning("Odoo connection check failed at startup: %s", exc)
    try:
        yield {"odoo": odoo}
    finally:
        pass

mcp = FastMCP("McpErpServer", lifespan=app_lifespan)

from tools.create_invoice import create_invoice
# from tools.get_invoice import get_invoice
# from tools.update_invoice import update_invoice

mcp.add_tool(create_invoice)
# mcp.add_tool(get_invoice)
# mcp.add_tool(update_invoice)

if __name__ == "__main__":
    mcp.run(transport="stdio")