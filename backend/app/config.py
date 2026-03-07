from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    APP_NAME: str = "Smart ERP"

    DATABASE_URL: str = "postgresql://user:password@localhost/smart_erp"

    LLM_PROVIDER: str = "groq"
    GROQ_API_KEY: str 

    class Config:
        env_file = ".env"


settings = Settings()