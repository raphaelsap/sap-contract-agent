import os

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _get_request_timeout() -> float:
    for candidate in (
        os.getenv("REQUEST_TIMEOUT"),
        os.getenv("SAP_AICORE_REQUEST_TIMEOUT"),
    ):
        if candidate:
            try:
                return float(candidate)
            except ValueError:
                continue
    return 120.0


@dataclass
class Settings:
    sap_aicore_client_id: str
    sap_aicore_client_secret: str
    sap_aicore_auth_url: str
    sap_aicore_api_base: str
    sap_aicore_deployment_id: str
    sap_aicore_resource_group: str
    sap_aicore_scope: Optional[str]
    sap_aicore_api_version: str
    data_storage_path: Path
    artefact_storage_path: Path
    chat_completions_path: Optional[str]
    request_timeout: float

    @classmethod
    def from_env(cls) -> "Settings":
        data_storage = Path(os.getenv("DATA_STORAGE_PATH", "data"))
        artefact_storage = Path(os.getenv("ARTEFACT_STORAGE_PATH", "artefacts"))
        chat_path = os.getenv("SAP_AICORE_CHAT_COMPLETIONS_PATH")
        timeout = _get_request_timeout()

        settings = cls(
            sap_aicore_client_id=os.getenv("SAP_AICORE_CLIENT_ID", ""),
            sap_aicore_client_secret=os.getenv("SAP_AICORE_CLIENT_SECRET", ""),
            sap_aicore_auth_url=os.getenv("SAP_AICORE_AUTH_URL", ""),
            sap_aicore_api_base=os.getenv("SAP_AICORE_API_BASE", ""),
            sap_aicore_deployment_id=os.getenv("SAP_AICORE_DEPLOYMENT_ID", ""),
            sap_aicore_resource_group=os.getenv("SAP_AICORE_RESOURCE_GROUP", "default"),
            sap_aicore_scope=os.getenv("SAP_AICORE_SCOPE"),
            sap_aicore_api_version=os.getenv("SAP_AICORE_API_VERSION", "2023-05-15"),
            data_storage_path=data_storage,
            artefact_storage_path=artefact_storage,
            chat_completions_path=chat_path,
            request_timeout=timeout,
        )

        settings.data_storage_path.mkdir(parents=True, exist_ok=True)
        settings.artefact_storage_path.mkdir(parents=True, exist_ok=True)
        return settings


settings = Settings.from_env()
