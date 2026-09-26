"""Settings opcionales de Azure AI Foundry para la validación local."""

from __future__ import annotations

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AzureLlmConfigurationError(RuntimeError):
    """Config Azure inválida o incompleta; mensajes sin eco de secretos."""


class AzureLlmSettings(BaseSettings):
    """Variables Foundry usadas solo por el módulo/script de validación."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    endpoint: str = Field(validation_alias="FLOWSIGHT_AZURE_AI_ENDPOINT", min_length=1)
    api_key: SecretStr = Field(validation_alias="FLOWSIGHT_AZURE_AI_API_KEY", min_length=1)
    deployment: str = Field(validation_alias="FLOWSIGHT_AZURE_AI_DEPLOYMENT", min_length=1)
    api_version: str | None = Field(default=None, validation_alias="FLOWSIGHT_AZURE_AI_API_VERSION")
    region: str | None = Field(default=None, validation_alias="FLOWSIGHT_AZURE_AI_REGION")
    model_name: str | None = Field(default=None, validation_alias="FLOWSIGHT_AZURE_AI_MODEL")
    model_selection_notes: str | None = Field(
        default=None, validation_alias="FLOWSIGHT_AZURE_AI_MODEL_NOTES"
    )
    openai_base_url: str | None = Field(
        default=None, validation_alias="FLOWSIGHT_AZURE_OPENAI_ENDPOINT"
    )

    @field_validator("endpoint", "deployment")
    @classmethod
    def reject_whitespace_only(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value.strip()

    @field_validator("api_key")
    @classmethod
    def reject_blank_api_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("must not be empty")
        return value

    def resolve_openai_base_url(self) -> str:
        """Base URL OpenAI-compatible (…/openai/v1) para el cliente."""

        if self.openai_base_url and self.openai_base_url.strip():
            return self.openai_base_url.rstrip("/")
        base = self.endpoint.rstrip("/")
        if base.endswith("/openai/v1"):
            return base
        return f"{base}/openai/v1"


def load_azure_llm_settings() -> AzureLlmSettings:
    """Carga settings Azure o falla con causa accionable sin revelar secretos."""

    try:
        return AzureLlmSettings()
    except ValidationError as error:
        problems: list[str] = []
        for detail in error.errors(include_input=False, include_url=False):
            variable = str(detail["loc"][0])
            error_type = str(detail["type"])
            cause = _cause_for(error_type, str(detail["msg"]))
            problems.append(
                f"{variable}: {cause}. Completá la sección Azure de .env.example "
                "solo para el script de validación (API/worker no la exigen)."
            )
        raise AzureLlmConfigurationError(
            "Configuración Azure inválida: " + " ".join(problems)
        ) from None


def _cause_for(error_type: str, message: str) -> str:
    if error_type == "missing":
        return "missing"
    if error_type == "string_too_short" or "must not be empty" in message:
        return "empty"
    return "invalid_format"
