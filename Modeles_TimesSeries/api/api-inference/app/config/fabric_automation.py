"""
Automatisation Fabric depuis l'API locale :
1) upload du fichier outbox dans OneLake (API DFS)
2) déclenchement d'un Notebook Fabric (REST API)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Any
from urllib.parse import quote

import httpx

from app.settings import (
    FABRIC_AUTOMATION_ENABLED,
    FABRIC_TENANT_ID,
    FABRIC_CLIENT_ID,
    FABRIC_CLIENT_SECRET,
    ONELAKE_WORKSPACE_NAME,
    ONELAKE_LAKEHOUSE_NAME,
    ONELAKE_OUTBOX_REMOTE_PATH,
    FABRIC_WORKSPACE_ID,
    FABRIC_NOTEBOOK_ITEM_ID,
    FABRIC_NOTEBOOK_TRIGGER_PAYLOAD,
)

logger = logging.getLogger(__name__)


class FabricAutomationError(RuntimeError):
    """Erreur d'automatisation Fabric (upload OneLake ou trigger Notebook)."""


def _validate_common_config() -> None:
    required = {
        "FABRIC_TENANT_ID": FABRIC_TENANT_ID,
        "FABRIC_CLIENT_ID": FABRIC_CLIENT_ID,
        "FABRIC_CLIENT_SECRET": FABRIC_CLIENT_SECRET,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise FabricAutomationError(
            "Configuration Fabric manquante: " + ", ".join(missing)
        )


def _get_client_credentials_token(scope: str) -> str:
    _validate_common_config()

    token_url = f"https://login.microsoftonline.com/{FABRIC_TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": FABRIC_CLIENT_ID,
        "client_secret": FABRIC_CLIENT_SECRET,
        "scope": scope,
    }

    with httpx.Client(timeout=60) as client:
        response = client.post(token_url, data=data)
        if response.status_code >= 400:
            raise FabricAutomationError(
                f"AAD token error ({response.status_code}): {response.text[:400]}"
            )

        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise FabricAutomationError("AAD access_token absent de la réponse")
        return token


def upload_outbox_to_onelake(local_outbox_path: Path) -> Dict[str, Any]:
    if not local_outbox_path.exists():
        raise FabricAutomationError(f"Outbox introuvable: {local_outbox_path}")

    required = {
        "ONELAKE_WORKSPACE_NAME": ONELAKE_WORKSPACE_NAME,
        "ONELAKE_LAKEHOUSE_NAME": ONELAKE_LAKEHOUSE_NAME,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise FabricAutomationError(
            "Configuration OneLake manquante: " + ", ".join(missing)
        )

    content = local_outbox_path.read_bytes()
    remote_path = ONELAKE_OUTBOX_REMOTE_PATH.lstrip("/")

    dfs_base = (
        "https://onelake.dfs.fabric.microsoft.com/"
        f"{quote(ONELAKE_WORKSPACE_NAME)}/{quote(ONELAKE_LAKEHOUSE_NAME)}.Lakehouse/"
        f"{quote(remote_path, safe='/')}"
    )

    storage_token = _get_client_credentials_token("https://storage.azure.com/.default")
    headers = {
        "Authorization": f"Bearer {storage_token}",
        "x-ms-version": "2023-11-03",
    }

    with httpx.Client(timeout=120) as client:
        create_resp = client.put(f"{dfs_base}?resource=file", headers=headers)
        if create_resp.status_code >= 400:
            raise FabricAutomationError(
                f"Create file OneLake error ({create_resp.status_code}): {create_resp.text[:400]}"
            )

        append_headers = {
            **headers,
            "Content-Type": "application/octet-stream",
        }
        append_resp = client.patch(
            f"{dfs_base}?action=append&position=0",
            headers=append_headers,
            content=content,
        )
        if append_resp.status_code >= 400:
            raise FabricAutomationError(
                f"Append file OneLake error ({append_resp.status_code}): {append_resp.text[:400]}"
            )

        flush_resp = client.patch(
            f"{dfs_base}?action=flush&position={len(content)}",
            headers=headers,
        )
        if flush_resp.status_code >= 400:
            raise FabricAutomationError(
                f"Flush file OneLake error ({flush_resp.status_code}): {flush_resp.text[:400]}"
            )

    logger.info("✅ Outbox uploadée vers OneLake")
    return {
        "remote_path": remote_path,
        "bytes_uploaded": len(content),
    }


def trigger_fabric_notebook() -> Dict[str, Any]:
    required = {
        "FABRIC_WORKSPACE_ID": FABRIC_WORKSPACE_ID,
        "FABRIC_NOTEBOOK_ITEM_ID": FABRIC_NOTEBOOK_ITEM_ID,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise FabricAutomationError(
            "Configuration Notebook Fabric manquante: " + ", ".join(missing)
        )

    fabric_token = _get_client_credentials_token("https://api.fabric.microsoft.com/.default")
    url = (
        "https://api.fabric.microsoft.com/v1/workspaces/"
        f"{FABRIC_WORKSPACE_ID}/items/{FABRIC_NOTEBOOK_ITEM_ID}/jobs/instances"
        "?jobType=RunNotebook"
    )
    headers = {
        "Authorization": f"Bearer {fabric_token}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=60) as client:
        response = client.post(url, headers=headers, json=FABRIC_NOTEBOOK_TRIGGER_PAYLOAD)
        if response.status_code >= 400:
            raise FabricAutomationError(
                f"Trigger Notebook error ({response.status_code}): {response.text[:500]}"
            )

        job = response.json() if response.text else {}

    logger.info("✅ Notebook Fabric déclenché")
    return job


def automate_onelake_upload_and_notebook(local_outbox_path: Path) -> Dict[str, Any]:
    """Pipeline complet local -> OneLake -> Notebook. Ne lève pas si disabled."""
    if not FABRIC_AUTOMATION_ENABLED:
        return {
            "enabled": False,
            "message": "Fabric automation disabled",
        }

    upload_result = upload_outbox_to_onelake(local_outbox_path)
    notebook_result = trigger_fabric_notebook()

    return {
        "enabled": True,
        "upload": upload_result,
        "notebook": notebook_result,
    }
