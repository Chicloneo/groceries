"""Pruebas de la orquestación y de cantidades seleccionadas."""

from decimal import Decimal

import pandas as pd

from proyecto_2.contracts import (
    Producto,
    ProductSelection,
    SelectionRequest,
    ShoppingRequest,
)
from proyecto_2 import shopping_flow

CATEGORY = "Huevos, leche y mantequilla"
SUBCATEGORY = "Leche y bebidas vegetales"


def make_product(*, quantity=8, unit="L"):
    return Producto(
        original_text="8 L de leche semidesnatada",
        pseudo_name="leche semidesnatada",
        search_terms=["leche semidesnatada"],
        requested_quantity=quantity,
        requested_unit=unit,
        features=[],
        categoria=CATEGORY,
        subcategoria=SUBCATEGORY,
    )


def make_request(*, quantity=8, unit="L"):
    return ShoppingRequest(
        request="Necesito 8 L de leche semidesnatada",
        cp="28012",
        products=[make_product(quantity=quantity, unit=unit)],
    )


def write_catalog(tmp_path, rows):
    path = tmp_path / "catalog.csv"
    pd.DataFrame(rows).to_csv(path, sep=";", index=False)
    return path


def row(name, *, price, amount, measure="ml", format="Brik 1 L"):
    return {
        "cp": "28012",
        "categoria": CATEGORY,
        "subcategoria": SUBCATEGORY,
        "nombre": name,
        "precio": price,
        "precio_por_": price,
        "unidades": "L" if measure == "ml" else "100 g",
        "formato": format,
        "es_pack": amount > 1000,
        "numero_unidades_pack": 6 if amount > 1000 else None,
        "numero_subunidades_pack_por_unidad": 1 if amount > 1000 else None,
        "cantidad producto": amount,
        "medida_producto": measure,
    }


def start_session(tmp_path, monkeypatch, rows):
    request = make_request()
    monkeypatch.setattr(shopping_flow, "parse_request", lambda text, cp=None: request)
    return shopping_flow.start_shopping(
        request.request,
        catalog_path=write_catalog(tmp_path, rows),
    )


def test_start_shopping_connects_request_parser_to_catalog_search(
    tmp_path, monkeypatch
):
    session = start_session(
        tmp_path,
        monkeypatch,
        [
            row("Leche semidesnatada 1 L", price=1, amount=1000),
            row(
                "Leche semidesnatada pack",
                price=6,
                amount=6000,
                format="6 briks x 1 L",
            ),
        ],
    )

    assert session.request.cp == "28012"
    assert len(session.searches) == 1
    assert session.searches[0]["status"] == "options"
    assert len(session.searches[0]["options"]) == 2


def test_selecting_pack_and_single_units_reaches_requested_volume(
    tmp_path, monkeypatch
):
    session = start_session(
        tmp_path,
        monkeypatch,
        [
            row("Leche semidesnatada 1 L", price=1.09, amount=1000),
            row(
                "Leche semidesnatada pack",
                price=6.54,
                amount=6000,
                format="6 briks x 1 L",
            ),
        ],
    )
    options = session.searches[0]["options"]
    one_liter_id = options[0]["option_id"]
    six_liter_id = options[1]["option_id"]
    monkeypatch.setattr(
        shopping_flow,
        "parse_selection",
        lambda text, offered: SelectionRequest(
            selections=[
                ProductSelection(option_id=six_liter_id, sale_quantity=1),
                ProductSelection(option_id=one_liter_id, sale_quantity=2),
            ],
            needs_clarification=False,
            clarification_question=None,
        ),
    )

    result = shopping_flow.select_for_product(session, 0, "un pack y dos briks")

    assert result["status"] == "target_met"
    assert result["selected_quantity"] == 8
    assert result["remaining_quantity"] == 0
    assert result["selected_total_price"] == 8.72
    assert result["basket_total_price"] == 8.72
    assert len(result["selections"]) == 2


def test_selection_can_accumulate_across_turns_until_target_is_met(
    tmp_path, monkeypatch
):
    session = start_session(
        tmp_path,
        monkeypatch,
        [
            row("Leche semidesnatada 1 L", price=1, amount=1000),
            row(
                "Leche semidesnatada pack",
                price=6,
                amount=6000,
                format="6 briks x 1 L",
            ),
        ],
    )
    options = session.searches[0]["options"]
    one_liter_id = options[0]["option_id"]
    six_liter_id = options[1]["option_id"]
    answers = iter(
        [
            SelectionRequest(
                selections=[
                    ProductSelection(option_id=six_liter_id, sale_quantity=1)
                ],
                needs_clarification=False,
                clarification_question=None,
            ),
            SelectionRequest(
                selections=[
                    ProductSelection(option_id=one_liter_id, sale_quantity=1)
                ],
                needs_clarification=False,
                clarification_question=None,
            ),
            SelectionRequest(
                selections=[
                    ProductSelection(option_id=one_liter_id, sale_quantity=1)
                ],
                needs_clarification=False,
                clarification_question=None,
            ),
        ]
    )
    monkeypatch.setattr(
        shopping_flow,
        "parse_selection",
        lambda text, offered: next(answers),
    )

    partial = shopping_flow.select_for_product(session, 0, "un pack")
    second_turn = shopping_flow.select_for_product(session, 0, "un brik más")
    completed = shopping_flow.select_for_product(session, 0, "otro brik")

    assert partial["status"] == "selection_recorded"
    assert partial["selected_quantity"] == 6
    assert partial["remaining_quantity"] == 2
    assert partial["target_met"] is False
    assert partial["selected_total_price"] == 6
    assert second_turn["selected_quantity"] == 7
    assert second_turn["remaining_quantity"] == 1
    assert second_turn["selected_total_price"] == 7
    assert completed["status"] == "target_met"
    assert completed["selected_quantity"] == 8
    assert completed["remaining_quantity"] == 0
    assert completed["target_met"] is True
    assert completed["selected_total_price"] == 8
    assert session.total_price == 8


def test_selection_converts_grams_to_requested_kilograms(tmp_path, monkeypatch):
    request = make_request(quantity=1, unit="kg")
    monkeypatch.setattr(shopping_flow, "parse_request", lambda text, cp=None: request)
    session = shopping_flow.start_shopping(
        request.request,
        catalog_path=write_catalog(
            tmp_path,
            [
                row(
                    "Leche semidesnatada polvo 500 g",
                    price=2,
                    amount=500,
                    measure="g",
                    format="Bolsa 500 g",
                )
            ],
        ),
    )
    option_id = session.searches[0]["options"][0]["option_id"]
    monkeypatch.setattr(
        shopping_flow,
        "parse_selection",
        lambda text, offered: SelectionRequest(
            selections=[ProductSelection(option_id=option_id, sale_quantity=2)],
            needs_clarification=False,
            clarification_question=None,
        ),
    )

    result = shopping_flow.select_for_product(session, 0, "dos bolsas")

    assert result["status"] == "target_met"
    assert result["selected_quantity"] == 1
    assert result["requested_unit"] == "kg"


def test_basket_total_sums_selections_from_multiple_requested_products(
    tmp_path, monkeypatch
):
    product = make_product(quantity=None, unit=None)
    request = ShoppingRequest(
        request="dos productos",
        cp="28012",
        products=[product, product.model_copy()],
    )
    monkeypatch.setattr(shopping_flow, "parse_request", lambda text, cp=None: request)
    session = shopping_flow.start_shopping(
        request.request,
        catalog_path=write_catalog(
            tmp_path,
            [row("Leche semidesnatada 1 L", price=1.09, amount=1000)],
        ),
    )

    def choose_one(text, offered):
        return SelectionRequest(
            selections=[
                ProductSelection(option_id=offered[0].option_id, sale_quantity=1)
            ],
            needs_clarification=False,
            clarification_question=None,
        )

    monkeypatch.setattr(shopping_flow, "parse_selection", choose_one)
    first = shopping_flow.select_for_product(session, 0, "una")
    second = shopping_flow.select_for_product(session, 1, "una")

    assert first["basket_total_price"] == 1.09
    assert second["selected_total_price"] == 1.09
    assert second["basket_total_price"] == 2.18
    assert session.total_price == Decimal("2.18")


def test_ambiguous_selection_does_not_change_accumulated_choices(
    tmp_path, monkeypatch
):
    session = start_session(
        tmp_path,
        monkeypatch,
        [row("Leche semidesnatada 1 L", price=1, amount=1000)],
    )
    monkeypatch.setattr(
        shopping_flow,
        "parse_selection",
        lambda text, offered: SelectionRequest(
            selections=[],
            needs_clarification=True,
            clarification_question="¿Qué opción eliges?",
        ),
    )

    result = shopping_flow.select_for_product(session, 0, "esa")

    assert result["status"] == "needs_clarification"
    assert result["selections"] == []
    assert session.selections == {}
