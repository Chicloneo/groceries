"""Búsqueda determinista de productos del catálogo preprocesado."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from .contracts import CatalogProduct, Producto, ProductOption, ShoppingRequest

PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG_PATH = (
    PROJECT_DIR.parent / "Data" / "Clean" / "preprocesado_1_madrid_centro.csv"
)
MAX_OPTIONS = 5
_STOPWORDS = {"a", "al", "de", "del", "el", "la", "las", "los", "y"}


def _tokens(text: str) -> list[str]:
    """Devuelve palabras relevantes, sin artículos ni preposiciones comunes."""
    return [
        token
        for token in re.findall(r"\w+", text.casefold())
        if token not in _STOPWORDS
    ]


def _contains_all_tokens(values: pd.Series, text: str) -> pd.Series:
    """Busca la intersección de filas que contienen cada palabra del texto."""
    tokens = _tokens(text)
    if not tokens:
        return pd.Series(False, index=values.index)

    mask = pd.Series(True, index=values.index)
    for token in tokens:
        mask &= values.str.contains(token, case=False, regex=False, na=False)
    return mask


def _load_catalog(path: str | Path) -> pd.DataFrame:
    """Carga el CSV conservando los códigos postales como texto."""
    catalog_path = Path(path)
    if not catalog_path.is_file():
        raise FileNotFoundError(f"No existe el catálogo: {catalog_path}")

    frame = pd.read_csv(
        catalog_path,
        sep=";",
        encoding="utf-8-sig",
        dtype={"cp": "string"},
    )
    required_columns = {
        "cp",
        "categoria",
        "subcategoria",
        "nombre",
        "precio",
        "precio_por_",
        "unidades",
        "formato",
        "es_pack",
        "numero_unidades_pack",
        "numero_subunidades_pack_por_unidad",
        "cantidad producto",
        "medida_producto",
    }
    missing = required_columns - set(frame.columns)
    if missing:
        raise ValueError(
            f"El catálogo no contiene las columnas requeridas: {sorted(missing)}"
        )
    return frame


def _product_mask(
    frame: pd.DataFrame,
    product: Producto,
    cp: str,
    *,
    include_features: bool = True,
    base_description_only: bool = False,
) -> pd.Series:
    """Filtra por CP, clasificación y texto del producto solicitado."""
    mask = frame["cp"].astype("string").str.strip().eq(cp)
    if product.categoria is not None:
        mask &= frame["categoria"].eq(product.categoria)
    if product.subcategoria is not None:
        mask &= frame["subcategoria"].eq(product.subcategoria)

    names = frame["nombre"].astype("string")
    terms = (
        [product.pseudo_name]
        if base_description_only
        else [product.pseudo_name, *product.search_terms]
    )
    text_mask = pd.Series(False, index=frame.index)
    for term in terms:
        text_mask |= _contains_all_tokens(names, term)
    mask &= text_mask

    # Los detalles expresos son requisitos adicionales. Se buscan en nombre y
    # formato para cubrir, por ejemplo, marcas y presentaciones del catálogo.
    if not include_features:
        return mask

    name_and_format = (
        names.fillna("")
        + " "
        + frame["formato"].astype("string").fillna("")
    )
    for feature in product.features:
        mask &= _contains_all_tokens(name_and_format, feature)
    return mask


def _serialize_option(row: pd.Series, option_id: str) -> dict[str, Any]:
    product = CatalogProduct.model_validate(row.to_dict())
    option = ProductOption(option_id=option_id, product=product)
    return option.model_dump(mode="json", by_alias=True)


def search(
    response: ShoppingRequest,
    catalog_path: str | Path = DEFAULT_CATALOG_PATH,
) -> list[dict[str, Any]]:
    """Busca hasta cinco opciones para cada producto de una petición.

    El CP, la categoría y la subcategoría restringen el catálogo. Las palabras
    relevantes de cada término se intersectan (ignorando preposiciones comunes)
    y los términos alternativos se combinan con OR. Cada atributo de
    ``features`` debe aparecer en el nombre o el formato. Si no existe ninguna
    fila con todos los ``features``, se devuelven todas las coincidencias de la
    descripción base junto con un aviso. La cantidad solicitada se conserva
    junto al producto, pero no filtra formatos ni calcula unidades.

    Cada resultado incluye el producto solicitado, un estado y ``options``.
    Si hay entre una y cinco coincidencias estrictas, se incluyen todas. Si hay
    más de cinco, no se elige un subconjunto: el resultado pide más detalle. El
    fallback por ``features`` devuelve toda la lista base, incluso si supera
    cinco opciones, y avisa de los detalles que no encontró. Las opciones
    contienen ``option_id`` y ``product`` y se pueden pasar después a
    ``parse_selection``.
    """
    if not response.products:
        return []

    if response.cp is None:
        return [
            {
                "request_product": product.model_dump(mode="json"),
                "status": "needs_postal_code",
                "match_count": 0,
                "clarification_question": "¿Cuál es tu código postal de cinco dígitos?",
                "options": [],
            }
            for product in response.products
        ]

    frame = _load_catalog(catalog_path)
    results: list[dict[str, Any]] = []

    for product_index, product in enumerate(response.products, start=1):
        matches = frame.loc[_product_mask(frame, product, response.cp)].copy()
        used_feature_fallback = False
        if matches.empty and product.features:
            # Si el nombre/categoría existen pero no hay fila que cumpla algún
            # detalle expreso (por ejemplo, una marca ausente), ofrecemos todas
            # las coincidencias de la descripción base y lo indicamos al usuario.
            matches = frame.loc[
                _product_mask(
                    frame,
                    product,
                    response.cp,
                    include_features=False,
                    base_description_only=True,
                )
            ].copy()
            used_feature_fallback = not matches.empty

        # El CSV puede repetir una fila idéntica. Distintos nombres, formatos o
        # precios siguen siendo opciones separadas.
        matches = matches.drop_duplicates()
        matches = matches.sort_values(
            [
                "nombre",
                "formato",
                "precio",
                "precio_por_",
                "unidades",
                "es_pack",
                "numero_unidades_pack",
                "numero_subunidades_pack_por_unidad",
                "cantidad producto",
                "medida_producto",
            ],
            kind="stable",
            na_position="last",
        ).reset_index(drop=True)

        result: dict[str, Any] = {
            "request_product": product.model_dump(mode="json"),
            "match_count": len(matches),
            "clarification_question": None,
            "notice": None,
            "options": [],
        }

        if matches.empty:
            result["status"] = "no_matches"
            results.append(result)
            continue

        if used_feature_fallback:
            result["notice"] = (
                "No encontré coincidencias que cumplan estos detalles: "
                f"{', '.join(product.features)}. Muestro todas las opciones "
                f"para «{product.pseudo_name}» sin esos detalles."
            )
        elif len(matches) > MAX_OPTIONS:
            result["status"] = "needs_clarification"
            result["clarification_question"] = (
                f"He encontrado {len(matches)} opciones para "
                f"«{product.pseudo_name}». ¿Puedes darme algún detalle más, "
                "como marca o formato?"
            )
            results.append(result)
            continue

        result["status"] = "options"
        result["options"] = [
            _serialize_option(row, f"producto-{product_index}-opcion-{option_index}")
            for option_index, (_, row) in enumerate(matches.iterrows(), start=1)
        ]
        results.append(result)

    return results
