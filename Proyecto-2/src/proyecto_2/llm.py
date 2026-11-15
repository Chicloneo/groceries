"""llm.py: natural language -> structured shopping request.

The rest of the app only calls `parse_request(text)`. Providers are adapters
behind a registry, so switching from Ollama to Gemini is a config change.

Environment variables
---------------------
LLM_PROVIDER      "ollama" (default) or "gemini"
LLM_MAX_ATTEMPTS  attempts per request, default 3

OLLAMA_MODEL      default "qwen3.5:4b"
OLLAMA_HOST       optional, default http://localhost:11434
OLLAMA_THINK      optional "true"/"false". Unset = parameter is not sent.
                  Some models have a slow "thinking" mode; check Ollama's docs
                  before setting this, since not every model supports it.

GEMINI_API_KEY    required when LLM_PROVIDER=gemini
GEMINI_MODEL      default "gemini-2.5-flash-lite" (check AI Studio for the
                  model ids currently available on the free tier)

Dependencies
------------
Local:       pip install pydantic ollama
Production:  pip install pydantic google-genai
Provider SDKs are imported lazily, so you only need the one you use.
"""

from __future__ import annotations

import logging
import os
import time
from functools import lru_cache
from typing import Callable, Literal

from pydantic import BaseModel, Field, ValidationError, Literal, field_validator

from categorias import CATEGORIAS, SUBCATEGORIAS

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------
# No default values on purpose: some versions of the Gemini SDK reject
# schemas that contain "default". The prompt tells the model what to fill in.

Unit = Literal['L','kg','100 g','ud','100 ml','docena','lavado','m']

class Producto(BaseModel):
    search_terms: list[str] = Field(
        description="2-3 ways a Spanish supermarket (Mercadona) might name this product, in Spanish."
    )
    quantity: float = Field(description="Amount requested. Use 1 if not stated.")
    unit: Unit | None = Field(
        description="Unit of the quantity, or null if not stated. Use 'units' for countable items."
    )

    cp: str | None = Field(pattern=r"^\d{5}$", description="User's zip code (cp, código postal). \
                    Use None if not stated")
    
    categoria: str | None = Field(description="Category of the product predicted by the ML model in Proyecto-1")

    subcategoria: str | None = Field(description="Subcategory of the product predicted by the ML model in Proyecto-1")

    nombre: str | None = Field(description=)

    # formato_y_precio_por_kilo: No la usamos

    precio: float | None = Field(description="Price of the product")
    precio_por_: float | None = Field(description="Price per [Unit]. This is specified in 'unidades'.")
    unidades: Unit | None = Field(description="Measure units (€/[Unit])")

    formato: str | None = Field(description="Way of product packaging: bottle, box, tray, brick...")

    es_pack: bool | None = Field(description="Wether the produc contains multiple units. Example: 6 bottle pack, 20 tea bags box, ...")
    numero_unidades_pack: int | None = Field(description="Number of units per product")
    numero_subunidades_pack_por_unidad: int | None = Field(description="Number of subunits per unit. Example: Pack of 2 ")

    cantidad_producto: float | None = Field(description="Total quantity of the product when you buy it \
                                            If it's a pack, this field adds up to total quantity")
    medida_producto: Unit = Field(description="Measure units")

    @field_validator("categoria", mode='before')
    @classmethod
    def validar_categoria(cls, value):
        if value not in CATEGORIAS:
            raise ValueError(f"El modelo falló al predecir la categoría \
                             {value} dentro de CATEGORIAS")

    @field_validator("subcategoria", mode='before')
    @classmethod
    def validar_subcategoria(cls, value):
        if value not in SUBCATEGORIAS:
            raise ValueError(f"El modelo falló al predecir la subcategoría \
                             {value} dentro de SUBCATEGORIAS")


class ShoppingRequest(BaseModel):
    items: list[Producto]


class LLMError(Exception):
    """Raised when the LLM could not produce a usable answer. Safe to show in the UI."""


SYSTEM_PROMPT = """\
You extract a shopping list from the user's message. The user may write in \
English or Spanish. Return one item per product.

Rules:
- search_terms: 2-3 Spanish names a supermarket could use for the product \
(synonyms, singular or plural). Never include brands unless the user names one.
- quantity: the number requested; 1 if not stated.
- unit: one of kg, g, l, ml, units; null if not stated. Use "units" for \
countable things ("3 apples", "a pack of yogurts").
- Ignore anything that is not a product to buy.

Examples:
User: I want to buy white beans
{"items": [{"search_terms": ["alubias blancas", "judías blancas"], "quantity": 1, "unit": null}]}

User: quiero 2 kg de patatas y una botella de leche
{"items": [{"search_terms": ["patatas", "patata"], "quantity": 2, "unit": "kg"},
           {"search_terms": ["leche"], "quantity": 1, "unit": "units"}]}
"""


# --------------------------------------------------------------------------
# Provider adapters: each takes the user text and returns a ShoppingRequest
# --------------------------------------------------------------------------

def _ollama(text: str) -> ShoppingRequest:
    import ollama  # lazy: not needed in production

    client = ollama.Client(host=os.getenv("OLLAMA_HOST") or None)

    extra: dict = {}
    think = os.getenv("OLLAMA_THINK")
    if think:
        extra["think"] = think.strip().lower() == "true"

    r = client.chat(
        model=os.getenv("OLLAMA_MODEL", "qwen3.5:4b"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        format=ShoppingRequest.model_json_schema(),
        options={"temperature": 0},
        **extra,
    )
    return ShoppingRequest.model_validate_json(r.message.content)


@lru_cache(maxsize=1)
def _gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise LLMError("GEMINI_API_KEY is not set.")

    from google import genai  # lazy: not needed locally

    return genai.Client(api_key=api_key)


def _gemini(text: str) -> ShoppingRequest:
    from google.genai import types

    r = _gemini_client().models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=ShoppingRequest,
            temperature=0,
        ),
    )
    if isinstance(r.parsed, ShoppingRequest):
        return r.parsed
    # .parsed can be empty if validation failed; try the raw text ourselves.
    if r.text:
        return ShoppingRequest.model_validate_json(r.text)
    raise ValueError("Gemini returned no parseable output")


PROVIDERS: dict[str, Callable[[str], ShoppingRequest]] = {
    "ollama": _ollama,
    "gemini": _gemini,
}


# --------------------------------------------------------------------------
# Retries
# --------------------------------------------------------------------------

_RETRY_STATUS = {429, 500, 502, 503, 504}


def _status(exc: Exception) -> int | None:
    # google-genai errors expose .code; ollama errors expose .status_code
    return getattr(exc, "code", None) or getattr(exc, "status_code", None)


def _call_with_retries(fn: Callable[[str], ShoppingRequest], text: str) -> ShoppingRequest:
    attempts = max(1, int(os.getenv("LLM_MAX_ATTEMPTS", "3")))
    last: Exception | None = None

    for i in range(attempts):
        try:
            return fn(text)
        except (ValidationError, ValueError) as e:
            # Bad or empty output (small local models do this): just ask again.
            last = e
            log.warning("Invalid LLM output (attempt %d/%d): %s", i + 1, attempts, e)
        except Exception as e:
            if _status(e) in _RETRY_STATUS or isinstance(e, TimeoutError):
                last = e
                log.warning("Transient LLM error (attempt %d/%d): %s", i + 1, attempts, e)
                if i < attempts - 1:
                    time.sleep(2**i)  # 1s, 2s, 4s...
            else:
                raise  # auth errors, missing model, server down: retrying won't help

    raise LLMError(f"No valid answer after {attempts} attempts: {last}") from last


# --------------------------------------------------------------------------
# Cleanup + public API
# --------------------------------------------------------------------------

def _clean(req: ShoppingRequest) -> ShoppingRequest:
    items: list[Producto] = []
    for item in req.items:
        seen: set[str] = set()
        terms: list[str] = []
        for t in item.search_terms:
            t = " ".join(t.lower().split())
            if t and t not in seen:
                seen.add(t)
                terms.append(t)
        if not terms:
            continue
        qty = item.quantity if item.quantity and item.quantity > 0 else 1.0
        items.append(Producto(search_terms=terms, quantity=qty, unit=item.unit))
    return ShoppingRequest(items=items)


@lru_cache(maxsize=512)
def _cached_parse(provider: str, text: str) -> ShoppingRequest:
    try:
        raw = _call_with_retries(PROVIDERS[provider], text)
    except LLMError:
        raise
    except ConnectionError as e:
        hint = " Is `ollama serve` running?" if provider == "ollama" else ""
        raise LLMError(f"Could not reach {provider}.{hint}") from e
    except Exception as e:
        raise LLMError(f"{provider} call failed: {e}") from e
    return _clean(raw)


def clear_cache() -> None:
    """Call this if you change the model or provider while the app is running."""
    _cached_parse.cache_clear()


def parse_request(text: str) -> ShoppingRequest:
    """Turn free text into a ShoppingRequest. Raises LLMError on failure.

    Results are cached per (provider, normalized text); exceptions are not cached.
    """
    provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
    if provider not in PROVIDERS:
        raise LLMError(f"Unknown LLM_PROVIDER '{provider}'. Options: {', '.join(PROVIDERS)}")

    normalized = " ".join(text.lower().split())
    if not normalized:
        return ShoppingRequest(items=[])

    # Copy so callers can't mutate the cached object.
    return _cached_parse(provider, normalized).model_copy(deep=True)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    queries = sys.argv[1:] or [
        "I want to buy white beans",
        "quiero 2 kg de patatas y una botella de leche",
        "tomatoes, 500g of minced beef and 6 eggs",
    ]
    for q in queries:
        print(f"\n> {q}")
        try:
            print(parse_request(q).model_dump_json(indent=2))
        except LLMError as e:
            print(f"LLMError: {e}")