import contextvars
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request

# Nom de l'en-tête HTTP qui transporte l'ID de requête
REQUEST_ID_HEADER = "X-Request-ID"

# Context variable pour stocker l'ID de requête par contexte (thread/coroutine)
_request_id_ctx_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None,
)

# Nom du service pour le logger (modifiable via configure_logging)
_service_name = "api"


# ------------------- Formateur JSON pour les logs -------------------
class JsonFormatter(logging.Formatter):
    """
    Formateur de logs JSON léger.
    Permet d'ajouter automatiquement des champs supplémentaires
    tels que request_id, method, path, status_code, duration, etc.
    """

    # Liste des champs supplémentaires que l'on peut inclure dans les logs
    EXTRA_FIELDS = (
        "request_id",
        "method",
        "path",
        "status_code",
        "duration_ms",
        "client",
        "endpoint",
        "prm",
        "row_count",
        "column_count",
        "target_url",
        "upstream_service",
        "source",
    )

    def format(self, record: logging.LogRecord) -> str:
        """
        Transforme un LogRecord en JSON.
        """
        # Base du log
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", _service_name),
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Ajouter l'ID de requête si présent
        request_id = getattr(record, "request_id", None) or get_request_id()
        if request_id:
            payload["request_id"] = request_id

        # Ajouter tous les champs supplémentaires définis
        for field_name in self.EXTRA_FIELDS:
            value = getattr(record, field_name, None)
            if value is not None and field_name not in payload:
                payload[field_name] = value

        # Ajouter l'exception si elle existe
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


# ------------------- Configuration du logger principal -------------------
def configure_logging(service_name: str) -> logging.Logger:
    """
    Configure un logger JSON pour un service donné.
    
    Paramètres :
        service_name : nom du service pour identifier les logs
    
    Retour :
        Logger configuré
    """
    global _service_name
    _service_name = service_name

    logger = logging.getLogger(service_name)
    logger.setLevel(logging.INFO)

    # S'assurer que la configuration JSON n'est appliquée qu'une seule fois
    if not getattr(logger, "_structured_logging_configured", False):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.handlers = [handler]
        logger.propagate = False
        logger._structured_logging_configured = True

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Retourne un logger avec le nom du service ou un sous-logger.
    """
    if not name:
        return logging.getLogger(_service_name)
    return logging.getLogger(f"{_service_name}.{name}")


# ------------------- Gestion de l'ID de requête -------------------
def get_request_id() -> str | None:
    """
    Retourne l'ID de requête courant depuis le contexte.
    """
    return _request_id_ctx_var.get()


def build_correlation_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    """
    Construit les en-têtes HTTP de corrélation avec l'ID de requête.
    """
    merged_headers = dict(headers or {})
    request_id = get_request_id()
    if request_id and REQUEST_ID_HEADER not in merged_headers:
        merged_headers[REQUEST_ID_HEADER] = request_id
    return merged_headers


# ------------------- Middleware FastAPI pour enrichir le contexte -------------------
def install_request_context_middleware(app: FastAPI) -> None:
    """
    Middleware FastAPI pour gérer automatiquement :
    - l'ID de requête unique par requête
    - le calcul de la durée de traitement
    - l'ajout de logs JSON pour chaque requête HTTP
    """
    http_logger = get_logger("http")

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        # Récupérer l'ID de requête depuis les headers ou générer un UUID
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        token = _request_id_ctx_var.set(request_id)
        start = time.perf_counter()

        try:
            # Appel de la requête suivante dans la chaîne FastAPI
            response = await call_next(request)
        except Exception:
            # Log d'erreur si la requête échoue
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            http_logger.exception(
                "requete_echouee",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "client": request.client.host if request.client else None,
                    "duration_ms": duration_ms,
                },
            )
            _request_id_ctx_var.reset(token)
            raise

        # Calcul de la durée et ajout des headers
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        http_logger.info(
            "requete_terminee",
            extra={
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        # Réinitialiser le contexte
        _request_id_ctx_var.reset(token)
        return response