import pytest

from proyecto_1.loader import DataLoadError, load_catalog


def test_load_catalog_reads_csv_and_keeps_postal_code_as_text(tmp_path, products):
    path = tmp_path / "products.csv"
    products.to_csv(path, index=False)

    loaded = load_catalog(path)

    assert len(loaded) == len(products)
    assert str(loaded.loc[0, "cp"]) == "30370"


def test_load_catalog_raises_for_missing_file(tmp_path):
    with pytest.raises(DataLoadError, match="No existe"):
        load_catalog(tmp_path / "missing.csv")


def test_load_catalog_raises_when_required_columns_are_missing(tmp_path):
    path = tmp_path / "incomplete.csv"
    path.write_text("nombre\nAgua\n", encoding="utf-8")

    with pytest.raises(DataLoadError, match="Faltan columnas"):
        load_catalog(path)
