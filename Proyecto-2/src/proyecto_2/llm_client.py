"""Conexión estructurada a Groq y reintentos comunes."""

from __future__ import annotations

import logging
import os
import time
from typing import Callable, TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from .contracts import LLMError

log = logging.getLogger(__name__)
ResponseT = TypeVar("ResponseT", bound=BaseModel)


def _structured_chat(
    text: str,
    system_prompt: str,
    response_model: type[ResponseT],
) -> ResponseT:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise LLMError(
            "Falta GROQ_API_KEY. Configúrala en el entorno o en .env."
        )

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
    )
    response = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    if not content:
        raise LLMError("Groq devolvió una respuesta vacía.")
    return response_model.model_validate_json(content)


def _status(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    return status


def _call_with_retries(fn: Callable[[], ResponseT]) -> ResponseT:
    attempts = max(1, int(os.getenv("LLM_MAX_ATTEMPTS", "3")))
    last: Exception | None = None

    for attempt in range(attempts):
        try:
            return fn()
        except (ValidationError, ValueError) as exc:
            last = exc
            log.warning(
                "Salida LLM inválida (intento %d/%d): %s",
                attempt + 1,
                attempts,
                exc,
            )
        except Exception as exc:
            if _status(exc) in {429, 500, 502, 503, 504} or isinstance(
                exc, TimeoutError
            ):
                last = exc
                log.warning(
                    "Error temporal de Groq (intento %d/%d): %s",
                    attempt + 1,
                    attempts,
                    exc,
                )
                if attempt < attempts - 1:
                    time.sleep(2**attempt)
            else:
                raise

    raise LLMError(
        f"Sin respuesta válida después de {attempts} intentos: {last}"
    ) from last
