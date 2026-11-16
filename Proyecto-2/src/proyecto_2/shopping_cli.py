"""CLI interactivo para probar extracción, búsqueda y selección."""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

from .catalog_search import DEFAULT_CATALOG_PATH, search
from .contracts import LLMError
from .shopping_flow import (
    ShoppingSession,
    refine_product,
    select_for_product,
    start_shopping,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Interpreta una lista, busca opciones en el catálogo y registra "
            "las combinaciones elegidas."
        )
    )
    parser.add_argument(
        "request",
        nargs="?",
        help="Petición de compra entre comillas. Si se omite, se pregunta por consola.",
    )
    parser.add_argument(
        "--cp",
        help="Código postal de cinco dígitos; si se omite, se pregunta cuando haga falta.",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        help="CSV de catálogo (por defecto, Madrid centro preprocesado).",
    )
    return parser


def _read_shopping_request() -> str:
    print(
        "Escribe cada producto en una línea numerada. Incluye la cantidad y "
        "los detalles importantes (por ejemplo, marca o variedad)."
    )
    print(
        "Ejemplo:\n"
        "  1. 8 L de leche semidesnatada, marca Asturiana\n"
        "  2. 500 g de carne picada de cerdo"
    )
    return input("Lista de la compra: ").strip()


def _read_postal_code() -> str:
    while True:
        cp = input("Código postal de cinco dígitos: ").strip()
        if len(cp) == 5 and cp.isdigit():
            return cp
        print("Introduce un código postal de cinco dígitos.")


def _show_options(search_result: dict) -> None:
    product = search_result["request_product"]
    if search_result.get("notice"):
        print(f"\n{search_result['notice']}")
    print(f"\nProducto: {product['original_text']}")
    for position, option in enumerate(search_result["options"], start=1):
        catalog_product = option["product"]
        print(
            f"  Opción {position}: {catalog_product['nombre']} | "
            f"{catalog_product['formato']} | {catalog_product['precio']:.2f} €"
        )


def _show_selection(result: dict) -> None:
    for selection in result["selections"]:
        product = selection["product"]
        print(
            f"  {selection['sale_quantity']} × {product['nombre']} "
            f"({product['formato']})"
        )
    if result["selected_quantity"] is None:
        detail = result["quantity_status"]
        if detail == "quantity_not_specified":
            print("  Selección registrada; no se pidió una cantidad física.")
        else:
            print(
                "  Selección registrada; esta unidad solicitada no se puede "
                "comparar con el contenido físico del catálogo."
            )
        print(
            "  Total acumulado de este producto: "
            f"{result['selected_total_price']:.2f} €."
        )
        return

    unit = result["requested_unit"]
    print(
        f"  Acumulado: {result['selected_quantity']:g} {unit}; "
        f"restan {result['remaining_quantity']:g} {unit}."
    )
    print(
        "  Total acumulado de este producto: "
        f"{result['selected_total_price']:.2f} €."
    )


def _show_ticket(session: ShoppingSession) -> None:
    """Imprime líneas elegidas, precios unitarios, subtotales y total."""
    print("\nTicket final")
    for product_index, quantities in session.selections.items():
        product_request = session.request.products[product_index]
        options_by_id = {
            option["option_id"]: option["product"]
            for option in session.searches[product_index]["options"]
        }
        print(f"\n{product_request.original_text}")
        for option_id, sale_quantity in quantities.items():
            product = options_by_id[option_id]
            unit_price = Decimal(str(product["precio"]))
            line_total = unit_price * sale_quantity
            print(
                f"  {sale_quantity} × {product['nombre']} "
                f"({product['formato']}) | {unit_price:.2f} €/unidad | "
                f"{line_total:.2f} €"
            )
        print(f"  Subtotal: {session.product_totals[product_index]:.2f} €")
    print(f"\nTOTAL: {session.total_price:.2f} €")


def _collect_product_selection(
    session: ShoppingSession,
    product_index: int,
) -> None:
    product_request = session.request.products[product_index]
    search_result = session.searches[product_index]
    while search_result["status"] in {"needs_clarification", "no_matches"}:
        if search_result["status"] == "needs_clarification":
            prompt = search_result["clarification_question"]
        else:
            prompt = (
                f"No encontré opciones para «{product_request.pseudo_name}». "
                "¿Puedes reformularlo o añadir algún detalle?"
            )
        detail = input(f"{prompt} (o escribe «saltar»): ").strip()
        if detail.casefold() in {"saltar", "omitir"}:
            return
        try:
            updated = refine_product(session, product_index, detail)
        except LLMError as exc:
            print(f"No pude interpretar el detalle: {exc}")
            continue
        if not updated:
            print("No pude asociar ese detalle a un único producto. Prueba otra vez.")
            continue
        product_request = session.request.products[product_index]
        search_result = session.searches[product_index]

    if search_result["status"] == "needs_postal_code":
        print(search_result["clarification_question"])
        return
    if search_result["status"] != "options":
        print(f"No se pudo buscar «{product_request.pseudo_name}».")
        return

    _show_options(search_result)
    while True:
        answer = input(
            "Elige opciones y cantidades (p. ej. «dos de la opción 1»; "
            "«saltar» para continuar): "
        ).strip()
        if answer.casefold() in {"saltar", "omitir"}:
            return
        try:
            result = select_for_product(session, product_index, answer)
        except LLMError as exc:
            print(f"No se pudo interpretar la selección: {exc}")
            continue

        if result["status"] == "needs_clarification":
            print(result["clarification_question"])
            continue

        _show_selection(result)
        if result["status"] == "target_met":
            return
        if result["selected_quantity"] is None:
            return


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    text = args.request or _read_shopping_request()
    if not text:
        print("La petición está vacía.", file=sys.stderr)
        return 2

    catalog_path = args.catalog or DEFAULT_CATALOG_PATH
    try:
        session = start_shopping(text, cp=args.cp, catalog_path=catalog_path)
        if session.request.cp is None and session.request.products:
            cp = _read_postal_code()
            session.request = session.request.model_copy(update={"cp": cp})
            session.searches = search(session.request, catalog_path=catalog_path)
    except (LLMError, FileNotFoundError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not session.request.products:
        print("No he encontrado productos concretos en la petición.")
        return 0

    for product_index in range(len(session.request.products)):
        try:
            _collect_product_selection(session, product_index)
        except (LLMError, ValueError, OSError) as exc:
            print(f"Error al procesar la selección: {exc}", file=sys.stderr)
            return 2

    if session.product_totals:
        _show_ticket(session)
    else:
        print("\nFin de la prueba. No se seleccionaron productos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
