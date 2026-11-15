"""Interpretación de la selección del usuario entre opciones ofrecidas."""

from __future__ import annotations

import json
from typing import Sequence

from .contracts import ProductOption, ProductSelection, SelectionRequest, LLMError
from .ollama_client import _call_with_retries, _ollama
from .prompts import SELECTION_SYSTEM_PROMPT

def _validate_options(
    offered_options: Sequence[ProductOption | dict[str, object]],
) -> list[ProductOption]:
    """Valida opciones reales y exige un identificador único para cada una."""
    options = [
        option
        if isinstance(option, ProductOption)
        else ProductOption.model_validate(option)
        for option in offered_options
    ]
    option_ids = [option.option_id for option in options]
    if len(option_ids) != len(set(option_ids)):
        raise ValueError("Cada opción ofrecida debe tener un option_id único.")
    return options


def parse_selection(
    text: str,
    offered_options: Sequence[ProductOption | dict[str, object]],
) -> SelectionRequest:
    """Interpreta la selección del usuario entre opciones que ya vio.

    No busca en el catálogo. ``sale_quantity`` cuenta unidades comerciales
    (por ejemplo, dos envases del producto elegido), no litros o gramos pedidos.
    """
    options = _validate_options(offered_options)
    if not options:
        return SelectionRequest(
            selections=[],
            needs_clarification=True,
            clarification_question="No hay opciones pendientes para seleccionar.",
        )
    if not text.strip():
        return SelectionRequest(
            selections=[],
            needs_clarification=True,
            clarification_question="¿Qué opción quieres y cuántas unidades?",
        )

    # Entregamos al modelo el identificador estable y la posición visible de
    # cada opción. La posición permite entender «la segunda»; Python valida luego
    # que la respuesta use un identificador que realmente se ofreció.
    options_json = json.dumps(
        [
            {
                "position": position,
                **option.model_dump(mode="json", by_alias=True),
            }
            for position, option in enumerate(options, start=1)
        ],
        ensure_ascii=False,
    )
    prompt = (
        "Opciones disponibles (datos procedentes del catálogo):\n"
        f"{options_json}\n\n"
        "Respuesta del usuario a estas opciones:\n"
        f"{text}"
    )
    try:
        result = _call_with_retries(
            lambda: _ollama(
                prompt,
                SELECTION_SYSTEM_PROMPT,
                SelectionRequest,
            )
        )
    except LLMError:
        raise
    except ConnectionError as exc:
        raise LLMError("No se pudo conectar con Ollama. ¿Está iniciado `ollama serve`?") from exc
    except Exception as exc:
        raise LLMError(f"Falló la interpretación de la selección: {exc}") from exc

    if result.needs_clarification or not result.selections:
        return SelectionRequest(
            selections=[],
            needs_clarification=True,
            clarification_question=(
                result.clarification_question
                or "¿Qué opción quieres y cuántas unidades?"
            ),
        )

    valid_ids = {option.option_id for option in options}
    if any(selection.option_id not in valid_ids for selection in result.selections):
        return SelectionRequest(
            selections=[],
            needs_clarification=True,
            clarification_question="No he podido asociar la selección con las opciones mostradas. ¿Cuál eliges?",
        )

    # Si el modelo repite un ID, sumamos sus unidades en una sola selección.
    quantities: dict[str, int] = {}
    for selection in result.selections:
        quantities[selection.option_id] = (
            quantities.get(selection.option_id, 0) + selection.sale_quantity
        )
    return SelectionRequest(
        selections=[
            ProductSelection(option_id=option_id, sale_quantity=quantity)
            for option_id, quantity in quantities.items()
        ],
        needs_clarification=False,
        clarification_question=None,
    )

