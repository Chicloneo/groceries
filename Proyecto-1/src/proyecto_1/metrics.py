"""Agregaciones descriptivas del catálogo de productos."""

import pandas as pd


class MetricInputError(ValueError):
    """Los datos no contienen los campos necesarios para una métrica."""


def _price_data(products: pd.DataFrame) -> pd.DataFrame:
    required = {"categoria", "precio_unidad"}
    missing = sorted(required - set(products.columns))
    if missing:
        raise MetricInputError(
            f"Faltan columnas requeridas: {', '.join(missing)}"
        )

    result = products[["categoria", "precio_unidad"]].copy()
    price_text = (
        result["precio_unidad"]
        .astype("string")
        .str.replace("€", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip()
    )
    result["precio_unidad"] = pd.to_numeric(price_text, errors="coerce")
    if result["precio_unidad"].isna().any():
        raise MetricInputError("Hay precios vacíos o no numéricos.")
    if (result["precio_unidad"] <= 0).any():
        raise MetricInputError("Todos los precios deben ser mayores que cero.")
    if result["categoria"].isna().any() or result["categoria"].astype("string").str.strip().eq("").any():
        raise MetricInputError("Hay categorías vacías.")
    return result


def average_price_by_category(products: pd.DataFrame) -> pd.DataFrame:
    """Calcula el precio medio por envase de cada categoría."""
    data = _price_data(products)
    return (
        data.groupby("categoria", as_index=False)["precio_unidad"]
        .mean()
        .round({"precio_unidad": 2})
        .rename(columns={"precio_unidad": "precio_medio"})
        .sort_values(["precio_medio", "categoria"], ignore_index=True)
    )


def product_counts(products: pd.DataFrame) -> dict[str, list[dict[str, object]]]:
    """Cuenta nombres de producto distintos por categoría y subcategoría."""
    required = {"categoria", "subcategoria", "nombre"}
    missing = sorted(required - set(products.columns))
    if missing:
        raise MetricInputError(
            f"Faltan columnas requeridas: {', '.join(missing)}"
        )

    category_counts = (
        products.groupby("categoria")["nombre"]
        .nunique()
        .rename("productos")
        .reset_index()
    )
    subcategory_counts = (
        products.groupby(["categoria", "subcategoria"])["nombre"]
        .nunique()
        .rename("productos")
        .reset_index()
    )

    def leaders(counts: pd.DataFrame) -> list[dict[str, object]]:
        if counts.empty:
            return []
        largest = counts["productos"].max()
        return counts.loc[counts["productos"].eq(largest)].to_dict(
            orient="records"
        )

    return {
        "categorias_con_mas_productos": leaders(category_counts),
        "subcategorias_con_mas_productos": leaders(subcategory_counts),
    }


def category_price_extremes(
    average_prices: pd.DataFrame,
) -> dict[str, list[dict[str, object]]]:
    """Devuelve las categorías con menor y mayor precio medio por envase."""
    if not {"categoria", "precio_medio"} <= set(average_prices.columns):
        raise MetricInputError(
            "Se requieren las columnas categoria y precio_medio."
        )
    if average_prices.empty:
        return {"mas_baratas": [], "mas_caras": []}

    cheapest = average_prices["precio_medio"].min()
    most_expensive = average_prices["precio_medio"].max()
    return {
        "mas_baratas": average_prices.loc[
            average_prices["precio_medio"].eq(cheapest)
        ].to_dict(orient="records"),
        "mas_caras": average_prices.loc[
            average_prices["precio_medio"].eq(most_expensive)
        ].to_dict(orient="records"),
    }


def most_common_container(
    products: pd.DataFrame,
) -> list[dict[str, object]]:
    """Cuenta envases por fila, excluyendo el marcador de revisión."""
    if "envase" not in products.columns:
        raise MetricInputError("Falta la columna requerida: envase")
    containers = products["envase"].dropna()
    containers = containers.loc[containers.ne("Revisar nombre")]
    counts = containers.value_counts()
    if counts.empty:
        return []
    return [
        {"envase": container, "apariciones": int(count)}
        for container, count in counts.items()
        if count == counts.max()
    ]


def calculate_metrics(products: pd.DataFrame) -> dict[str, object]:
    """Calcula el conjunto de métricas acordado para el catálogo."""
    average_prices = average_price_by_category(products)
    return {
        "precio_medio_por_categoria": average_prices.to_dict(orient="records"),
        "extremos_de_precio_medio": category_price_extremes(average_prices),
        **product_counts(products),
        "envases_mas_frecuentes": most_common_container(products),
    }
