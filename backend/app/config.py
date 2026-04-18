from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    APP_NAME: str = "Smart ERP"

    DATABASE_URL: str = "postgresql://user:password@localhost/smart_erp"

    LLM_PROVIDER: str = "groq"
    GROQ_API_KEY: str 

    # Odoo — used by MCP server via stdio env pass
    odoo_url: str = "http://localhost:8069"
    odoo_db: str = ""
    odoo_api_key: str = ""

    # Keep these if you still use old JSON-RPC auth anywhere
    odoo_username: str = ""
    odoo_password: str = ""

    # MCP server
    mcp_server_path: str = "../mcp-erp-server"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )



settings = Settings()