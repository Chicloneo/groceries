import json
from decimal import Decimal

from ..ai_client import structured_chat as _structured_chat
from ..groq import _call_with_retries
from .contracts import ProductSelection, SelectionRequest


SELECTION_PROMPT = """\
Interpreta qué opciones eligió el usuario y cuántas unidades comerciales quiere.
Devuelve exclusivamente JSON con este formato:
{
  "selections": [
    {"option_id": "producto-1-opcion-1", "sale_quantity": 2}
  ],
  "needs_clarification": false,
  "clarification_question": null
}

Usa solo option_id que aparezcan en las opciones proporcionadas.
sale_quantity cuenta unidades comerciales: botellas, cajas, paquetes o unidades.
Si solo menciona una opción sin cantidad, sale_quantity es 1.
No inventes precios ni totales.
"""


def buscar_opcion_por_numero(
    texto: str,
    opciones: list[dict],
) -> dict | None:
    numero = texto.strip()
    if not numero.isdigit():
        return None

    posicion = int(numero)
    if not 1 <= posicion <= len(opciones):
        return None
    return opciones[posicion - 1]


def sumar_cesta(cesta: dict[str, int], opciones: dict[str, dict]) -> Decimal:
    total = Decimal("0")
    for option_id, cantidad in cesta.items():
        precio = opciones[option_id]["product"]["precio"]
        total += Decimal(str(precio)) * cantidad
    return total


def interpretar_seleccion(
    texto: str,
    opciones: list[dict],
) -> SelectionRequest:
    """Interpreta la elección: números en Python y texto libre con Groq."""
    if not opciones:
        return SelectionRequest(
            selections=[],
            needs_clarification=True,
            clarification_question="No hay opciones pendientes para seleccionar.",
        )

    opcion = buscar_opcion_por_numero(texto, opciones)
    if opcion is not None:
        return SelectionRequest(
            selections=[
                ProductSelection(
                    option_id=opcion["option_id"],
                    sale_quantity=1,
                )
            ],
            needs_clarification=False,
            clarification_question=None,
        )

    opciones_json = json.dumps(
        [
            {
                "position": position,
                **opcion,
            }
            for position, opcion in enumerate(opciones, start=1)
        ],
        ensure_ascii=False,
    )
    prompt = (
        "Opciones disponibles:\n"
        f"{opciones_json}\n\n"
        "Respuesta del usuario:\n"
        f"{texto}"
    )
    if texto.strip().isdigit():
        posicion = int(texto.strip())
        if 1 <= posicion <= len(opciones):
            prompt += (
                "\n\nIndicación inequívoca: la respuesta contiene solo "
                f"un número ({posicion}). Debes seleccionar la opción "
                f"en la posición {posicion}, con sale_quantity: 1."
            )

    result = _call_with_retries(
        lambda: _structured_chat(
            prompt,
            SELECTION_PROMPT,
            SelectionRequest,
        )
    )

    valid_ids = {opcion["option_id"] for opcion in opciones}
    if any(
        seleccion.option_id not in valid_ids
        for seleccion in result.selections
    ):
        return SelectionRequest(
            selections=[],
            needs_clarification=True,
            clarification_question=(
                "No pude asociar la selección con las opciones mostradas."
            ),
        )

    cantidades: dict[str, int] = {}
    for seleccion in result.selections:
        cantidades[seleccion.option_id] = (
            cantidades.get(seleccion.option_id, 0)
            + seleccion.sale_quantity
        )

    return SelectionRequest(
        selections=[
            ProductSelection(option_id=option_id, sale_quantity=cantidad)
            for option_id, cantidad in cantidades.items()
        ],
        needs_clarification=result.needs_clarification,
        clarification_question=result.clarification_question,
    )
