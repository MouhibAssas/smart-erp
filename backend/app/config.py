from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    APP_NAME: str = "Smart ERP"

    DATABASE_URL: str 

    LLM_PROVIDER: str = "groq"
    GROQ_API_KEY: str 

    # Odoo — used by MCP server via stdio env pass
    odoo_url: str = "http://localhost:8069"
    odoo_db: str = ""
    odoo_api_key: str = ""

    # MCP server
    mcp_server_path: str = "../mcp-erp-server"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )



settings = Settings()