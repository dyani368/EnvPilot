from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./envpilot.db"
    envpilot_max_ttl_hours: int = 24
    envpilot_approver_ids: str = "approver-1"
    envpilot_fake_failure: str = "none"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
