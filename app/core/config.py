from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "mialma"
    DATABASE_URL: str = "sqlite+aiosqlite:///./sql_app.db"

    MIGADU_USER: str
    MIGADU_TOKEN: str

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
