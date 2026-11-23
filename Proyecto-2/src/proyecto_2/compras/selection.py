import re
import json
from decimal import Decimal

from ..groq import _call_with_retries, _structured_chat
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


_NUMBER_WORDS = {
    "una": 1,
    "un": 1,
    "uno": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
}


def intentar_seleccion_determinista(
    texto: str,
    opciones: list[dict],
) -> SelectionRequest | None:
    """Interpreta frases claras sin llamar a Groq."""
    limpio = " ".join(texto.strip().lower().replace(",", " ").split())
    if not limpio:
        return None

    if limpio.isdigit():
        posicion = int(limpio)
        if 1 <= posicion <= len(opciones):
            opcion = opciones[posicion - 1]
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

    selections: list[ProductSelection] = []
    covered_spans: list[tuple[int, int]] = []
    cantidad_numero = re.compile(
        r"(?P<cantidad>\d+|una?|un|dos|tres|cuatro|cinco|seis|siete|"
        r"ocho|nueve|diez)\s+(?:de\s+(?:la\s+)?)?"
        r"(?P<posicion>\d+)",
        re.IGNORECASE,
    )
    for patron in cantidad_numero.finditer(limpio):
        cantidad_texto = patron.group("cantidad").lower()
        if cantidad_texto in _NUMBER_WORDS:
            cantidad = _NUMBER_WORDS[cantidad_texto]
        elif cantidad_texto.isdigit():
            cantidad = int(cantidad_texto)
        else:
            continue

        posicion = int(patron.group("posicion"))
        if not 1 <= posicion <= len(opciones):
            continue
        selections.append(
            ProductSelection(
                option_id=opciones[posicion - 1]["option_id"],
                sale_quantity=cantidad,
            )
        )
        covered_spans.append(patron.span())

    cantidad_opcion = re.compile(
        r"(?P<cantidad>\d+|una?|un|dos|tres|cuatro|cinco|seis|siete|"
        r"ocho|nueve|diez)\s+(?:de\s+(?:la\s+)?)?"
        r"opci[oó]n\s*(?P<posicion>\d+)",
        re.IGNORECASE,
    )
    for patron in cantidad_opcion.finditer(limpio):
        cantidad_texto = patron.group("cantidad").lower()
        if cantidad_texto in _NUMBER_WORDS:
            cantidad = _NUMBER_WORDS[cantidad_texto]
        elif cantidad_texto.isdigit():
            cantidad = int(cantidad_texto)
        else:
            return None

        posicion = int(patron.group("posicion"))
        if not 1 <= posicion <= len(opciones):
            return None
        selections.append(
            ProductSelection(
                option_id=opciones[posicion - 1]["option_id"],
                sale_quantity=cantidad,
            )
        )
        covered_spans.append(patron.span())

    for patron in re.finditer(
        r"opci[oó]n\s*(?P<posicion>\d+)",
        limpio,
        re.IGNORECASE,
    ):
        if any(
            patron.start() >= start and patron.end() <= end
            for start, end in covered_spans
        ):
            continue
        posicion = int(patron.group("posicion"))
        if not 1 <= posicion <= len(opciones):
            return None
        selections.append(
            ProductSelection(
                option_id=opciones[posicion - 1]["option_id"],
                sale_quantity=1,
            )
        )

    if not selections:
        return None

    cantidades: dict[str, int] = {}
    for seleccion in selections:
        cantidades[seleccion.option_id] = (
            cantidades.get(seleccion.option_id, 0)
            + seleccion.sale_quantity
        )

    return SelectionRequest(
        selections=[
            ProductSelection(option_id=option_id, sale_quantity=cantidad)
            for option_id, cantidad in cantidades.items()
        ],
        needs_clarification=False,
        clarification_question=None,
    )


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


def extraer_opcion_y_cantidad(
    texto: str,
    opciones: list[dict],
) -> tuple[dict | None, int]:
    """Devuelve la opción y la cantidad expresada por el usuario."""
    cantidad = 1
    cantidad_antes_opcion = re.search(
        r"^(\d+)\s+(?:de\s+)?(?:la\s+)?opci[oó]n\s*(\d+)",
        texto.strip(),
        re.IGNORECASE,
    )
    if cantidad_antes_opcion:
        cantidad = int(cantidad_antes_opcion.group(1))
        posicion = int(cantidad_antes_opcion.group(2))
        opcion = (
            opciones[posicion - 1]
            if 1 <= posicion <= len(opciones)
            else None
        )
    else:
        opcion = buscar_opcion_por_numero(texto, opciones)
        if opcion is None:
            opcion_numero = re.search(
                r"opci[oó]n\s*(\d+)",
                texto,
                re.IGNORECASE,
            )
            if opcion_numero:
                posicion = int(opcion_numero.group(1))
                opcion = (
                    opciones[posicion - 1]
                    if 1 <= posicion <= len(opciones)
                    else None
                )

    if opcion is not None:
        for coincidencia in re.findall(
            r"(\d+)\s*(?:unidades|uds?\.?|packs?)",
            texto,
            re.IGNORECASE,
        ):
            cantidad = int(coincidencia)
            break

    if cantidad < 1:
        cantidad = 1
    return opcion, cantidad


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
    """Usa Groq para interpretar la elección y valida los IDs en Python."""
    if not opciones:
        return SelectionRequest(
            selections=[],
            needs_clarification=True,
            clarification_question="No hay opciones pendientes para seleccionar.",
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
