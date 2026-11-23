from functools import lru_cache
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[3]
CATALOG_PATH = PROJECT_DIR.parent / "Data" / "Clean" / "preprocesado_1_madrid_centro.csv"


# Guarda una vez el mapa calculado para no releer y procesar el CSV en cada llamada.
@lru_cache(maxsize=1)
def cargar_mapa_categoria_subcategoria() -> dict[str, list[str]]:
    """Lee el catálogo y crea el mapa categoría -> subcategorías."""
    frame = pd.read_csv(CATALOG_PATH, sep=";", encoding="utf-8-sig")

    category_subcategories = {} # es de tipo dict[str, set[str]]

    relationships = frame[["categoria", "subcategoria"]].dropna().drop_duplicates()

    for category, subcategory in relationships.itertuples(index=False, name=None):
        category = str(category)
        subcategory = str(subcategory)
        category_subcategories.setdefault(category, set()).add(subcategory)

    mapa = {}
    for category in sorted(category_subcategories):
        subcategories = sorted(category_subcategories[category])
        mapa[category] = subcategories

    return mapa
