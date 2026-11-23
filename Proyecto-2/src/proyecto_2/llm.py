"""Interfaz pública del pipeline de lenguaje natural.

La implementación se divide por responsabilidad: modelos, prompts, cliente de
Groq, extracción de pedidos e interpretación de selecciones. Este módulo
conserva los imports y el comando CLI existentes.
"""

import logging
import sys

from .contracts import (
    CatalogProduct, LLMError, Producto, ProductOption, ProductSelection,
    SelectionRequest, ShoppingRequest, Unit, RequestedUnit, ProductMeasure,
)
from .request_parser import clear_cache, parse_request
from .selection_parser import parse_selection

__all__ = [
    "CatalogProduct", "LLMError", "Producto", "ProductOption",
    "ProductSelection", "SelectionRequest", "ShoppingRequest", "Unit",
    "RequestedUnit", "ProductMeasure", "clear_cache", "parse_request",
    "parse_selection",
]

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    queries = sys.argv[1:] or [
        "Necesito comprar 6 L de leche semidesnatada y carne picada",
        "Quiero patatas fritas onduladas Hacendado y dos packs de yogur natural",
        "500 g de lentejas pardinas y 6 huevos",
    ]
    for q in queries:
        print(f"\n> {q}")
        try:
            print(parse_request(q).model_dump_json(indent=2))
        except LLMError as e:
            print(f"LLMError: {e}")
