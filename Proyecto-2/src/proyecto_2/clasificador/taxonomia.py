from functools import lru_cache
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[3]
CATALOG_PATH = PROJECT_DIR.parent / "Proyecto-1" / "catalogo_mercadona.csv"


@lru_cache(maxsize=1)
def cargar_mapa_categoria_subcategoria() -> dict[str, list[str]]:
    frame = pd.read_csv(CATALOG_PATH)
    mapa: dict[str, set[str]] = {}

    for category, subcategory in frame[
        ["categoria", "subcategoria"]
    ].dropna().drop_duplicates().itertuples(index=False, name=None):
        mapa.setdefault(str(category), set()).add(str(subcategory))

    return {
        category: sorted(subcategories)
        for category, subcategories in sorted(mapa.items())
    }
