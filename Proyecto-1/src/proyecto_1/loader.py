"""Carga del catálogo de productos desde CSV."""

from pathlib import Path

import pandas as pd

from proyecto_1.contracts import ProductoMercadona


class DataLoadError(ValueError):
    """Error al leer o reconocer el CSV del catálogo."""


REQUIRED_COLUMNS = tuple(ProductoMercadona.model_fields)


def load_catalog(path: str | Path) -> pd.DataFrame:
    """Carga un CSV conservando los códigos postales como texto."""
    csv_path = Path(path).expanduser()
    if not csv_path.is_file():
        raise DataLoadError(f"No existe el CSV de entrada: {csv_path}")

    try:
        catalog = pd.read_csv(
            csv_path,
            dtype={"cp": "string"},
            encoding="utf-8-sig",
        )
    except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise DataLoadError(f"No se pudo leer el CSV {csv_path}: {exc}") from exc

    missing = sorted(set(REQUIRED_COLUMNS) - set(catalog.columns))
    if missing:
        raise DataLoadError(
            f"Faltan columnas requeridas en {csv_path}: {', '.join(missing)}"
        )
    return catalog
