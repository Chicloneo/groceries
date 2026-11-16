"""Orquestación de petición, búsqueda y selección de productos."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from .catalog_search import DEFAULT_CATALOG_PATH, search
from .contracts import Producto, ProductOption, ShoppingRequest
from .request_parser import parse_request
from .selection_parser import parse_selection

_REQUEST_TO_BASE: dict[str, tuple[str, Decimal]] = {
    "g": ("g", Decimal("1")),
    "kg": ("g", Decimal("1000")),
    "ml": ("ml", Decimal("1")),
    "L": ("ml", Decimal("1000")),
}


@dataclass
class ShoppingSession:
    """Petición interpretada, resultados del catálogo y elecciones acumuladas."""

    request: ShoppingRequest
    searches: list[dict[str, Any]]
    catalog_path: str | Path = DEFAULT_CATALOG_PATH
    selections: dict[int, dict[str, int]] = field(default_factory=dict)
    product_totals: dict[int, Decimal] = field(default_factory=dict)

    @property
    def total_price(self) -> Decimal:
        """Total de los productos elegidos hasta el momento."""
        return sum(self.product_totals.values(), Decimal("0"))


def start_shopping(
    text: str,
    cp: str | None = None,
    catalog_path: str | Path = DEFAULT_CATALOG_PATH,
) -> ShoppingSession:
    """Interpreta el texto y busca opciones para todos los productos pedidos."""
    request = parse_request(text, cp=cp)
    return ShoppingSession(
        request=request,
        searches=search(request, catalog_path=catalog_path),
        catalog_path=catalog_path,
    )


def refine_product(
    session: ShoppingSession,
    product_index: int,
    detail: str,
) -> bool:
    """Interpreta un detalle adicional y repite la búsqueda de ese producto.

    Devuelve ``False`` si el LLM no puede asociar la aclaración a un único
    producto. La cantidad original y sus características expresas se conservan.
    """
    if not 0 <= product_index < len(session.request.products):
        raise IndexError(f"No existe el producto solicitado: {product_index}")
    if not detail.strip():
        return False

    current = session.request.products[product_index]
    refined_request = parse_request(
        f"{current.original_text}. Aclaración: {detail.strip()}",
        cp=session.request.cp,
    )
    if len(refined_request.products) != 1:
        return False

    refined = refined_request.products[0]
    values = refined.model_dump()
    values["original_text"] = f"{current.original_text}. {detail.strip()}"
    if current.requested_quantity is not None:
        values["requested_quantity"] = current.requested_quantity
        values["requested_unit"] = current.requested_unit
    values["features"] = list(dict.fromkeys([*current.features, *refined.features]))
    if refined.categoria is None:
        values["categoria"] = current.categoria
    if refined.subcategoria is None:
        values["subcategoria"] = current.subcategoria
    refined = Producto.model_validate(values)

    products = list(session.request.products)
    products[product_index] = refined
    session.request = session.request.model_copy(update={"products": products})
    refined_request = session.request.model_copy(update={"products": [refined]})
    session.searches[product_index] = search(
        refined_request,
        catalog_path=session.catalog_path,
    )[0]
    session.selections.pop(product_index, None)
    session.product_totals.pop(product_index, None)
    return True


def _amount_in_requested_unit(
    session: ShoppingSession,
    product_index: int,
    options_by_id: dict[str, ProductOption],
    quantities: dict[str, int],
) -> tuple[Decimal | None, str | None]:
    """Suma el contenido seleccionado y lo expresa en la unidad solicitada."""
    product_request = session.request.products[product_index]
    requested_quantity = product_request.requested_quantity
    requested_unit = product_request.requested_unit
    if requested_quantity is None or requested_unit is None:
        return None, "quantity_not_specified"
    if requested_unit not in _REQUEST_TO_BASE:
        return None, "quantity_unit_not_comparable"

    requested_measure, requested_factor = _REQUEST_TO_BASE[requested_unit]
    total_base = Decimal("0")
    for option_id, sale_quantity in quantities.items():
        catalog_product = options_by_id[option_id].product
        if catalog_product.cantidad_producto is None:
            return None, "catalog_quantity_missing"
        if catalog_product.medida_producto != requested_measure:
            return None, "incompatible_quantity_units"
        total_base += (
            Decimal(str(catalog_product.cantidad_producto))
            * sale_quantity
        )
    return total_base / requested_factor, None


def select_for_product(
    session: ShoppingSession,
    product_index: int,
    text: str,
) -> dict[str, Any]:
    """Interpreta y acumula una selección para un producto de la sesión.

    ``product_index`` es de base cero, como los índices de listas Python.
    Puede llamarse varias veces para que la persona complete la cantidad pedida.
    El intérprete solo identifica opciones y unidades comerciales; Python suma
    el contenido físico desde los datos validados del catálogo.
    """
    if not 0 <= product_index < len(session.searches):
        raise IndexError(f"No existe el producto solicitado: {product_index}")

    search_result = session.searches[product_index]
    if search_result["status"] != "options":
        return {
            "status": search_result["status"],
            "clarification_question": search_result["clarification_question"],
            "selections": [],
        }

    offered_options = [
        ProductOption.model_validate(option)
        for option in search_result["options"]
    ]
    parsed = parse_selection(text, offered_options)
    if parsed.needs_clarification:
        return {
            "status": "needs_clarification",
            "clarification_question": parsed.clarification_question,
            "selections": [],
        }

    options_by_id = {option.option_id: option for option in offered_options}
    accumulated = session.selections.setdefault(product_index, {})
    for selection in parsed.selections:
        accumulated[selection.option_id] = (
            accumulated.get(selection.option_id, 0) + selection.sale_quantity
        )

    selected_total_price = sum(
        (
            Decimal(str(options_by_id[option_id].product.precio))
            * sale_quantity
            for option_id, sale_quantity in accumulated.items()
        ),
        Decimal("0"),
    )
    session.product_totals[product_index] = selected_total_price

    selected_quantity, quantity_error = _amount_in_requested_unit(
        session,
        product_index,
        options_by_id,
        accumulated,
    )
    product_request = session.request.products[product_index]
    result: dict[str, Any] = {
        "status": "selection_recorded",
        "clarification_question": None,
        "selections": [
            {
                "option_id": option_id,
                "sale_quantity": quantity,
                "product": options_by_id[option_id].product.model_dump(
                    mode="json", by_alias=True
                ),
            }
            for option_id, quantity in accumulated.items()
        ],
        "requested_quantity": product_request.requested_quantity,
        "requested_unit": product_request.requested_unit,
        "selected_quantity": (
            float(selected_quantity) if selected_quantity is not None else None
        ),
        "quantity_status": quantity_error,
        "remaining_quantity": None,
        "target_met": None,
        "selected_total_price": float(selected_total_price),
        "basket_total_price": float(session.total_price),
    }

    if selected_quantity is not None:
        target = Decimal(str(product_request.requested_quantity))
        remaining = max(target - selected_quantity, Decimal("0"))
        result["remaining_quantity"] = float(remaining)
        result["target_met"] = selected_quantity >= target
        if selected_quantity >= target:
            result["status"] = "target_met"
    return result
