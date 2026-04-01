import os
from fastapi import Header, HTTPException, status


def require_api_key(x_api_key: str | None = Header(default=None)) -> str:
    expected_key = os.getenv("INFERENCE_API_KEY", "dev-inference-key")

    if x_api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API invalide ou manquante"
        )

    return x_api_key
