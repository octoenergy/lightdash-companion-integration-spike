import pydantic
import pydantic_settings


class Settings(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(env_file=".env", extra="ignore")

    lightdash_url: str
    lightdash_token: str
    project_uuid: str
    lightdash_admin_token: str | None = None
    agent_uuid: str | None = None
    embed_secret: str | None = None
    sandbox_space_slug: str | None = None
    openai_api_key: str | None = None
    log_level: str = "INFO"

    @pydantic.field_validator(
        "lightdash_admin_token",
        "agent_uuid",
        "embed_secret",
        "sandbox_space_slug",
        "openai_api_key",
        mode="before",
    )
    @classmethod
    def _blank_means_unset(cls, value: object) -> object:
        # .env templates leave optional keys as `KEY=`, which would otherwise be sent as "".
        return None if value == "" else value


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # required fields are read from the environment
