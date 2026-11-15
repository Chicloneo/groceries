"""Conexión estructurada a Ollama y política común de reintentos."""

from __future__ import annotations

import logging
import os
import time
from typing import Callable, TypeVar

from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)
ResponseT = TypeVar("ResponseT", bound=BaseModel)

ResponseT = TypeVar("ResponseT", bound=BaseModel)


def _ollama(
    text: str,
    system_prompt: str,
    response_model: type[ResponseT],
) -> ResponseT:
    """Pide a Ollama una respuesta JSON ajustada al esquema Pydantic recibido."""
    import ollama  # Importación diferida: solo se necesita al llamar al modelo.

    client = ollama.Client(host=os.getenv("OLLAMA_HOST") or None)

    extra: dict = {}
    think = os.getenv("OLLAMA_THINK")
    if think:
        extra["think"] = think.strip().lower() == "true"

    r = client.chat(
        model=os.getenv("OLLAMA_MODEL", "qwen3.5:4b"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        format=response_model.model_json_schema(),
        options={"temperature": 0},
        **extra,
    )
    # r.message.thinking imprime cómo "piensa" el modelo
    return response_model.model_validate_json(r.message.content)


# --------------------------------------------------------------------------
# Reintentos
# --------------------------------------------------------------------------

_RETRY_STATUS = {429, 500, 502, 503, 504}


def _status(exc: Exception) -> int | None:
    """Código HTTP de excepciones de Ollama/httpx, si está disponible."""
    return getattr(exc, "status_code", None)


def _call_with_retries(fn: Callable[[], ResponseT]) -> ResponseT:
    """Repite la llamada ante JSON inválido o errores temporales de conexión."""
    attempts = max(1, int(os.getenv("LLM_MAX_ATTEMPTS", "3")))
    last: Exception | None = None

    for i in range(attempts):
        try:
            return fn()
        except (ValidationError, ValueError) as e:
            # Una respuesta vacía o inválida puede ser temporal; se vuelve a pedir.
            last = e
            log.warning("Salida LLM inválida (intento %d/%d): %s", i + 1, attempts, e)
        except Exception as e:
            if _status(e) in _RETRY_STATUS or isinstance(e, TimeoutError):
                last = e
                log.warning("Error temporal de Ollama (intento %d/%d): %s", i + 1, attempts, e)
                if i < attempts - 1:
                    time.sleep(2**i)  # Espera 1, 2 y 4 segundos entre reintentos.
            else:
                raise  # Por ejemplo: modelo no instalado o parámetros incorrectos.

    raise LLMError(f"Sin respuesta válida después de {attempts} intentos: {last}") from last



