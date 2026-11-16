"""Casos deterministas para la búsqueda por CP y clasificación."""

import pandas as pd

from proyecto_2.catalog_search import search
from proyecto_2.contracts import Producto, ShoppingRequest

CATEGORY = "Huevos, leche y mantequilla"
SUBCATEGORY = "Leche y bebidas vegetales"


def make_product(
    *,
    pseudo_name="leche",
    search_terms=None,
    features=None,
    category=CATEGORY,
    subcategory=SUBCATEGORY,
):
    return Producto(
        original_text=pseudo_name,
        pseudo_name=pseudo_name,
        search_terms=search_terms or [pseudo_name],
        requested_quantity=8,
        requested_unit="L",
        features=features or [],
        categoria=category,
        subcategoria=subcategory,
    )


def make_row(
    name,
    *,
    cp="28012",
    category=CATEGORY,
    subcategory=SUBCATEGORY,
    price=1.0,
    format="Brik 1 L",
    amount=1000,
    measure="ml",
):
    return {
        "cp": cp,
        "categoria": category,
        "subcategoria": subcategory,
        "nombre": name,
        "precio": price,
        "precio_por_": price,
        "unidades": "L",
        "formato": format,
        "es_pack": False,
        "numero_unidades_pack": None,
        "numero_subunidades_pack_por_unidad": None,
        "cantidad producto": amount,
        "medida_producto": measure,
    }


def write_catalog(tmp_path, rows):
    path = tmp_path / "catalog.csv"
    pd.DataFrame(rows).to_csv(path, sep=";", index=False)
    return path


def make_request(products=None, cp="28012"):
    return ShoppingRequest(
        request="quiero leche",
        cp=cp,
        products=products or [make_product()],
    )


def test_search_returns_all_up_to_five_and_keeps_distinct_prices(tmp_path):
    rows = [
        make_row("Leche semidesnatada", price=1.0, format="Brik 1 L"),
        make_row("Leche semidesnatada", price=1.2, format="Brik 1 L"),
        make_row("Leche entera", price=1.1, format="Brik 1 L"),
        make_row("Leche semidesnatada", cp="28013"),
    ]
    path = write_catalog(tmp_path, rows)

    result = search(make_request(), catalog_path=path)[0]

    assert result["status"] == "options"
    assert result["match_count"] == 3
    assert [option["product"]["nombre"] for option in result["options"]] == [
        "Leche entera",
        "Leche semidesnatada",
        "Leche semidesnatada",
    ]
    assert [option["product"]["precio"] for option in result["options"]] == [
        1.1,
        1.0,
        1.2,
    ]
    assert len(result["options"]) <= 5


def test_search_requests_more_detail_when_there_are_more_than_five(tmp_path):
    rows = [
        make_row(f"Leche semidesnatada marca {number}", price=number + 1)
        for number in range(6)
    ]
    result = search(make_request(), catalog_path=write_catalog(tmp_path, rows))[0]

    assert result["status"] == "needs_clarification"
    assert result["match_count"] == 6
    assert result["options"] == []
    assert "detalle" in result["clarification_question"]


def test_search_reports_no_matches_and_does_not_search_other_postcodes(tmp_path):
    rows = [make_row("Leche semidesnatada", cp="28013")]
    result = search(make_request(), catalog_path=write_catalog(tmp_path, rows))[0]

    assert result["status"] == "no_matches"
    assert result["options"] == []


def test_search_requires_postal_code_before_loading_catalog(tmp_path):
    request = make_request(cp=None)

    result = search(request, catalog_path=tmp_path / "missing.csv")[0]

    assert result["status"] == "needs_postal_code"
    assert result["options"] == []


def test_search_applies_explicit_features_to_name_or_format(tmp_path):
    rows = [
        make_row("Leche semidesnatada", format="Brik 1 L"),
        make_row("Leche semidesnatada sin lactosa", format="Brik 1 L"),
    ]
    product = make_product(features=["sin lactosa"])
    result = search(
        make_request(products=[product]),
        catalog_path=write_catalog(tmp_path, rows),
    )[0]

    assert result["status"] == "options"
    assert [option["product"]["nombre"] for option in result["options"]] == [
        "Leche semidesnatada sin lactosa"
    ]
