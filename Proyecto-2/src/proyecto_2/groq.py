"""Conexión estructurada a Groq y reintentos comunes."""

from __future__ import annotations

import logging
import json
import os
import time
from typing import Callable, TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from .compras.contracts import LLMError

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

    data = json.loads(content)
    if response_model.__name__ == "_ShoppingRequestPayload":
        data = _normalize_shopping_payload(data)
    return response_model.model_validate(data)


def _normalize_shopping_payload(data: object) -> dict:
    """Acepta la forma singular que algunos modelos devuelven."""
    if not isinstance(data, dict):
        return {"cp": None, "products": []}

    products = data.get("products")
    if not isinstance(products, list):
        singular = data.get("product")
        if isinstance(singular, dict):
            products = [singular]
        elif isinstance(singular, str) and singular.strip():
            products = [{
                "original_text": singular,
                "pseudo_name": singular,
            }]
        else:
            products = []

    normalized_products = []
    for product in products:
        if not isinstance(product, dict):
            continue

        name = (
            product.get("original_text")
            or product.get("pseudo_name")
            or product.get("product")
            or product.get("name")
        )
        if not name:
            continue

        pseudo_name = product.get("pseudo_name") or name
        search_terms = product.get("search_terms")
        if not isinstance(search_terms, list) or not search_terms:
            search_terms = [pseudo_name]

        features = product.get("features")
        if not isinstance(features, list):
            features = []

        normalized_products.append({
            "original_text": str(name),
            "pseudo_name": str(pseudo_name),
            "search_terms": [str(term) for term in search_terms],
            "requested_quantity": product.get("requested_quantity", product.get("quantity")),
            "requested_unit": product.get("requested_unit", product.get("unit")),
            "features": [str(feature) for feature in features],
            "categoria": product.get("categoria"),
            "subcategoria": product.get("subcategoria"),
        })

    cp = data.get("cp")
    if not isinstance(cp, str):
        cp = None
    return {"cp": cp, "products": normalized_products}


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
