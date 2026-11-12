import pytest

from proyecto_1.validator import validate_catalog


def test_validate_catalog_separates_valid_and_invalid_rows(products):
    products.loc[1, "precio_unidad"] = "0,00 €"

    valid, invalid = validate_catalog(products)

    assert len(valid) == 3
    assert len(invalid) == 1
    assert invalid.iloc[0]["row_number"] == 2
    assert "precio_unidad" in invalid.iloc[0]["validation_error"]


@pytest.mark.parametrize("price", ["0 €", "-1 €"])
def test_validate_catalog_rejects_nonpositive_prices(price, products):
    products = products.iloc[[0]].copy()
    products.loc[products.index[0], "precio_unidad"] = price

    valid, invalid = validate_catalog(products)

    assert valid.empty
    assert len(invalid) == 1


def test_validate_catalog_keeps_exact_duplicate_rows(products):
    duplicate = products.iloc[[0]]
    repeated = duplicate.loc[duplicate.index.repeat(2)].reset_index(drop=True)

    valid, invalid = validate_catalog(repeated)

    assert len(valid) == 2
    assert invalid.empty
