"""Selecciona el proveedor de IA usado por el proyecto."""

from __future__ import annotations

import json
import os
import re
from typing import TypeVar

from pydantic import BaseModel

from .groq import _structured_chat as groq_structured_chat


ResponseT = TypeVar("ResponseT", bound=BaseModel)


def _mock_shopping_request(text: str, response_model: type[ResponseT]) -> ResponseT:
    from .compras.contracts import Producto, _ShoppingRequestPayload

    cp_match = re.search(r"\b\d{5}\b", text)
    cp = cp_match.group(0) if cp_match else None

    if text.strip().casefold() in {"", "nada", "ninguno"}:
        return _ShoppingRequestPayload(cp=cp, products=[])

    original_text = text.strip()
    if cp:
        original_text = re.sub(r"\b\d{5}\b", "", original_text).strip()
    product = Producto(
        original_text=original_text,
        pseudo_name=original_text,
        search_terms=[original_text],
        requested_quantity=None,
        requested_unit=None,
        features=[],
        categoria=None,
        subcategoria=None,
    )
    return _ShoppingRequestPayload(cp=cp, products=[product])


def _mock_selection(text: str, response_model: type[ResponseT]) -> ResponseT:
    from .compras.contracts import ProductSelection, SelectionRequest

    match = re.search(r"Respuesta del usuario:\s*(.+)", text, re.DOTALL)
    answer = match.group(1).strip() if match else text.strip()

    try:
        options_text = text.split("Opciones disponibles:\n", 1)[1]
        options_text = options_text.split("\n\nRespuesta del usuario:", 1)[0]
        options = json.loads(options_text)
    except (IndexError, json.JSONDecodeError):
        options = []

    if answer.isdigit():
        position = int(answer)
        if 1 <= position <= len(options):
            return SelectionRequest(
                selections=[
                    ProductSelection(
                        option_id=options[position - 1]["option_id"],
                        sale_quantity=1,
                    )
                ],
                needs_clarification=False,
                clarification_question=None,
            )
        return SelectionRequest(
            selections=[],
            needs_clarification=True,
            clarification_question="¿Qué opción quieres y cuántas unidades?",
        )

    quantity_match = re.search(
        r"\b(\d+)\b.*\b(?:opci[oó]n|opcion)\s*(\d+)\b",
        answer,
        re.IGNORECASE,
    )
    if not quantity_match:
        option_match = re.search(
            r"\b(?:opci[oó]n|opcion)\s*(\d+)\b",
            answer,
            re.IGNORECASE,
        )
        if not option_match:
            return SelectionRequest(
                selections=[],
                needs_clarification=True,
                clarification_question="¿Qué opción quieres y cuántas unidades?",
            )
        quantity = 1
        position = int(option_match.group(1))
    else:
        quantity = int(quantity_match.group(1))
        position = int(quantity_match.group(2))

    if not 1 <= position <= len(options):
        return SelectionRequest(
            selections=[],
            needs_clarification=True,
            clarification_question="¿Qué opción quieres y cuántas unidades?",
        )

    return SelectionRequest(
        selections=[
            ProductSelection(
                option_id=options[position - 1]["option_id"],
                sale_quantity=quantity,
            )
        ],
        needs_clarification=False,
        clarification_question=None,
    )


def structured_chat(
    text: str,
    system_prompt: str,
    response_model: type[ResponseT],
) -> ResponseT:
    provider = os.getenv("AI_PROVIDER", "groq").strip().casefold()

    if provider == "mock":
        if response_model.__name__ == "SelectionRequest":
            return _mock_selection(text, response_model)
        if response_model.__name__ == "_ShoppingRequestPayload":
            return _mock_shopping_request(text, response_model)
        raise ValueError(
            f"El proveedor mock no admite el modelo {response_model.__name__}"
        )

    if provider == "groq":
        return groq_structured_chat(text, system_prompt, response_model)

    raise ValueError(
        f"AI_PROVIDER debe ser 'mock' o 'groq', recibido: {provider}"
    )
