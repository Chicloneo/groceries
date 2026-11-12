import pandas as pd

from proyecto_1.metrics import (
    average_price_by_category,
    calculate_metrics,
    category_price_extremes,
    most_common_container,
    product_counts,
)


def test_average_price_by_category_uses_all_rows(products):
    averages = average_price_by_category(products).set_index("categoria")

    assert averages.loc["Bebidas", "precio_medio"] == 3.0
    assert averages.loc["Zumos", "precio_medio"] == 2.0


def test_average_price_by_category_rounds_to_two_decimals():
    products = pd.DataFrame(
        {
            "categoria": ["Bebidas", "Bebidas", "Bebidas"],
            "precio_unidad": ["1,00 €", "1,00 €", "2,00 €"],
        }
    )

    averages = average_price_by_category(products)

    assert averages.loc[0, "precio_medio"] == 1.33


def test_product_counts_use_unique_names_not_formats_or_duplicate_rows(products):
    duplicate = products.iloc[[0]].copy()
    products = pd.concat([products, duplicate], ignore_index=True)

    counts = product_counts(products)

    assert counts["categorias_con_mas_productos"] == [
        {"categoria": "Zumos", "productos": 2}
    ]
    assert counts["subcategorias_con_mas_productos"] == [
        {
            "categoria": "Zumos",
            "subcategoria": "Naranja",
            "productos": 2,
        }
    ]


def test_category_price_extremes_use_category_means(products):
    averages = average_price_by_category(products)

    extremes = category_price_extremes(averages)

    assert extremes["mas_baratas"] == [
        {"categoria": "Zumos", "precio_medio": 2.0}
    ]
    assert extremes["mas_caras"] == [
        {"categoria": "Bebidas", "precio_medio": 3.0}
    ]


def test_most_common_container_excludes_review_placeholder(products):
    assert most_common_container(products) == [
        {"envase": "Botella", "apariciones": 2}
    ]


def test_calculate_metrics_returns_all_requested_summaries(products):
    report = calculate_metrics(products)

    assert "precio_medio_por_categoria" in report
    assert "categorias_con_mas_productos" in report
    assert "subcategorias_con_mas_productos" in report
    assert "extremos_de_precio_medio" in report
    assert "envases_mas_frecuentes" in report
