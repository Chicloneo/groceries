"""Extracción y normalización de una petición de compra."""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

from ..clasificador.classifier import ProductClassifier
from ..groq import _call_with_retries, _structured_chat
from .contracts import Producto, ShoppingRequest, _ShoppingRequestPayload, LLMError


SYSTEM_PROMPT = """\
Convierte la petición de compra en JSON conforme al esquema.
No inventes productos, nombres oficiales, formatos, precios ni disponibilidad.
Conserva cantidades y unidades pedidas por el usuario.
Usa null si falta una información.
"""


@lru_cache(maxsize=1)
def _load_classifier() -> ProductClassifier:
    """Carga una vez el clasificador ya entrenado guardado en models/."""
    return ProductClassifier.load()


def _normalizar_lista(valores: Sequence[str]) -> list[str]:
    """Limpia espacios y duplicados conservando la escritura del usuario."""
    resultado: list[str] = []
    vistos: set[str] = set()
    for valor in valores:
        limpio = " ".join(valor.split())
        clave = limpio.casefold()
        if limpio and clave not in vistos:
            resultado.append(limpio)
            vistos.add(clave)
    return resultado


def _clean_payload(payload: _ShoppingRequestPayload) -> _ShoppingRequestPayload:
    """Limpia la extracción y clasifica cada fragmento de producto con Python."""
    if not payload.products:
        return _ShoppingRequestPayload(cp=payload.cp, products=[])

    # Se conserva la instrucción exacta correspondiente a cada producto como
    # entrada del clasificador; así, una lista con varios productos se predice
    # fila por fila en el mismo orden.
    predictions = _load_classifier().predict(
        [product.original_text for product in payload.products]
    )
    products: list[Producto] = []
    for product, prediction in zip(
        payload.products, predictions.itertuples(index=False)
    ):
        values = product.model_dump()
        values["pseudo_name"] = " ".join(product.pseudo_name.split())
        # La consulta principal siempre se conserva aunque el modelo solo haya
        # devuelto sinónimos adicionales en search_terms.
        values["search_terms"] = _normalizar_lista(
            [product.pseudo_name, *product.search_terms]
        )
        values["features"] = _normalizar_lista(product.features)
        values["categoria"] = prediction.categoria
        values["subcategoria"] = prediction.subcategoria
        products.append(Producto.model_validate(values))
    return _ShoppingRequestPayload(cp=payload.cp, products=products)


@lru_cache(maxsize=512)
def _cached_parse(text: str) -> _ShoppingRequestPayload:
    """Evita repetir una extracción idéntica durante la misma ejecución."""
    try:
        raw = _call_with_retries(
            lambda: _structured_chat(text, SYSTEM_PROMPT, _ShoppingRequestPayload)
        )
    except LLMError:
        raise
    except Exception as e:
        raise LLMError(f"Falló la llamada a Groq: {e}") from e
    return _clean_payload(raw)


def clear_cache() -> None:
    """Vacía extracción y modelo cargados, por ejemplo, si cambia el modelo."""
    _cached_parse.cache_clear()
    _load_classifier.cache_clear()


def parse_request(text: str, cp: str | None = None) -> ShoppingRequest:
    """Extrae productos, cantidades y CP del texto en lenguaje natural.

    ``cp`` permite pasar el CP que la aplicación ya guardó en la sesión. Si se
    proporciona, prevalece sobre el que se haya escrito en el mensaje.
    """
    normalized = " ".join(text.split())
    if not normalized:
        return ShoppingRequest(request=text, cp=cp, products=[])

    # Conserva el mensaje tal como lo escribió la persona para poder rastrear
    # cómo se interpretó. El CP de sesión evita pedirlo en cada consulta.
    payload = _cached_parse(normalized).model_copy(deep=True)
    return ShoppingRequest(
        request=text,
        cp=cp if cp is not None else payload.cp,
        products=payload.products,
    )



