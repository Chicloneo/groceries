"""Tests del clasificador de categorías y subcategorías."""

import pandas as pd
import pytest

from proyecto_2.classifier import (
    CATEGORY_COLUMN,
    NAME_COLUMN,
    SUBCATEGORY_COLUMN,
    ProductClassifier,
    fit_classifier,
    prepare_dataset,
    split_dataset,
)

PRODUCTS = {
    ("Huevos, leche y mantequilla", "Leche y bebidas vegetales"): [
        "Leche entera 1 L",
        "Leche semidesnatada 1 L",
        "Leche desnatada 1 L",
        "Bebida de avena 1 L",
        "Bebida de soja 1 L",
        "Leche sin lactosa 1 L",
    ],
    ("Huevos, leche y mantequilla", "Huevos y mantequilla"): [
        "Huevos frescos docena",
        "Huevos camperos docena",
        "Mantequilla natural 250 g",
        "Mantequilla sin sal 250 g",
        "Huevos ecológicos docena",
        "Mantequilla light 250 g",
    ],
    ("Limpieza y hogar", "Detergente y suavizante ropa"): [
        "Detergente líquido ropa 3 L",
        "Detergente en polvo ropa 2 kg",
        "Suavizante ropa primavera 2 L",
        "Detergente cápsulas 30 lavados",
        "Suavizante ropa bebé 1 L",
        "Detergente ropa color 3 L",
    ],
    ("Limpieza y hogar", "Papel higiénico y celulosa"): [
        "Papel higiénico 12 rollos",
        "Papel higiénico doble rollo",
        "Papel cocina absorbente",
        "Servilletas de papel 100 unidades",
        "Papel higiénico 4 capas",
        "Rollos de cocina gigantes",
    ],
}


def make_frame() -> pd.DataFrame:
    rows = [
        {
            NAME_COLUMN: name,
            CATEGORY_COLUMN: category,
            SUBCATEGORY_COLUMN: subcategory,
        }
        for (category, subcategory), names in PRODUCTS.items()
        for name in names
    ]
    return pd.DataFrame(rows)


def test_prepare_dataset_deduplicates_and_keeps_majority_label():
    frame = pd.DataFrame(
        {
            NAME_COLUMN: ["Producto repetido", "Producto repetido", "Producto repetido"],
            CATEGORY_COLUMN: ["Categoría A", "Categoría A", "Categoría B"],
            SUBCATEGORY_COLUMN: ["Sub A", "Sub A", "Sub B"],
        }
    )

    prepared = prepare_dataset(frame)

    assert len(prepared) == 1
    assert prepared.iloc[0][CATEGORY_COLUMN] == "Categoría A"
    assert prepared.iloc[0][SUBCATEGORY_COLUMN] == "Sub A"


def test_prepare_dataset_rejects_missing_columns():
    with pytest.raises(ValueError, match="Faltan columnas"):
        prepare_dataset(pd.DataFrame({NAME_COLUMN: ["Producto"]}))


def test_split_dataset_keeps_every_subcategory_in_test():
    train, test = split_dataset(make_frame(), test_size=0.25, random_state=42)

    assert len(train) + len(test) == len(make_frame())
    assert set(test[SUBCATEGORY_COLUMN]) == set(make_frame()[SUBCATEGORY_COLUMN])


def test_split_dataset_moves_real_rare_class_samples_to_cover_test():
    rows = []
    # Con solo dos productos por clase, el split aleatorio puede dejar ambos
    # ejemplos en el mismo conjunto.
    for subcategory_index in range(10):
        for product_index in range(2):
            rows.append(
                {
                    NAME_COLUMN: f"Producto raro {subcategory_index}-{product_index}",
                    CATEGORY_COLUMN: "Categoría",
                    SUBCATEGORY_COLUMN: f"Subcategoría rara {subcategory_index}",
                }
            )
    for subcategory_index in range(2):
        for product_index in range(20):
            rows.append(
                {
                    NAME_COLUMN: f"Producto común {subcategory_index}-{product_index}",
                    CATEGORY_COLUMN: "Categoría",
                    SUBCATEGORY_COLUMN: f"Subcategoría común {subcategory_index}",
                }
            )
    frame = pd.DataFrame(rows)

    train, test = split_dataset(frame, test_size=0.2, random_state=42)

    expected_subcategories = set(frame[SUBCATEGORY_COLUMN])
    assert set(train[SUBCATEGORY_COLUMN]) == expected_subcategories
    assert set(test[SUBCATEGORY_COLUMN]) == expected_subcategories
    assert set(train[NAME_COLUMN]).isdisjoint(test[NAME_COLUMN])


@pytest.mark.integration
def test_fit_predict_and_save_roundtrip(tmp_path):
    train, test = split_dataset(make_frame(), test_size=0.25, random_state=42)
    classifier = fit_classifier(train, test)

    assert classifier.metrics["accuracy_categoria_train"] == 1.0
    assert classifier.metrics["prueba"] == len(test)

    predictions = classifier.predict(
        ["Leche entera 2 L", "Detergente ropa 5 L"], top_k=2
    )
    assert list(predictions.columns) == [
        "nombre",
        "categoria",
        "confianza_categoria",
        "subcategoria",
        "confianza_subcategoria",
        "alternativas_subcategoria",
    ]
    assert predictions.iloc[0]["categoria"] == "Huevos, leche y mantequilla"
    assert predictions.iloc[1]["categoria"] == "Limpieza y hogar"

    model_path = tmp_path / "modelo.joblib"
    classifier.save(model_path)
    reloaded = ProductClassifier.load(model_path)

    pd.testing.assert_frame_equal(
        reloaded.predict(["Leche entera 2 L"]),
        classifier.predict(["Leche entera 2 L"]),
    )


def test_predict_rejects_empty_input():
    train, test = split_dataset(make_frame(), test_size=0.25, random_state=42)
    classifier = fit_classifier(train, test)

    with pytest.raises(ValueError, match="al menos un nombre"):
        classifier.predict([])
