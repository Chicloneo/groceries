import pandas as pd
import pytest


def product_row(
    *,
    name="Agua mineral",
    category="Bebidas",
    subcategory="Agua",
    price="1,00 €",
    container="Botella",
    product_format="Botella 1 L",
    **overrides,
):
    row = {
        "cp": "30370",
        "categoria": category,
        "subcategoria": subcategory,
        "nombre": name,
        "formato_y_precio_por_kilo": f"{product_format} | 1,00 €/L",
        "precio_unidad": price,
        "formato": product_format,
        "envase": container,
        "numero_unidades_venta": "1,0",
        "tipo_unidad_venta": container,
        "numero_unidades_contenido": "1,0",
        "tipo_unidad_contenido": container,
        "numero_unidades_contenido_total": "1,0",
        "cantidad_por_unidad": "1,0",
        "unidad_por_unidad": "L",
        "cantidad_neta": "1000,0",
        "unidad_neta": "ml",
        "cantidad_escurrida": "1000,0",
        "unidad_escurrida": "ml",
        "es_pack": False,
    }
    row.update(overrides)
    return row


@pytest.fixture
def products():
    return pd.DataFrame(
        [
            product_row(name="Agua mineral", price="2,00 €"),
            product_row(
                name="Agua mineral",
                price="4,00 €",
                product_format="Botella 2 L",
            ),
            product_row(
                name="Zumo",
                category="Zumos",
                subcategory="Naranja",
                price="1,00 €",
                container="Brik",
                product_format="Brik 1 L",
            ),
            product_row(
                name="Zumo premium",
                category="Zumos",
                subcategory="Naranja",
                price="3,00 €",
                container="Revisar nombre",
                product_format="Formato pendiente",
            ),
        ]
    )
