"""Validación de registros del catálogo."""

import pandas as pd
from pydantic import ValidationError as PydanticValidationError

from proyecto_1.contracts import ProductoMercadona
from proyecto_1.loader import REQUIRED_COLUMNS


class CatalogValidationError(ValueError):
    """El DataFrame no tiene la estructura necesaria para validarse."""


def validate_catalog(
    catalog: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa filas válidas e inválidas sin eliminar duplicados."""
    missing = sorted(set(REQUIRED_COLUMNS) - set(catalog.columns))
    if missing:
        raise CatalogValidationError(
            f"Faltan columnas requeridas: {', '.join(missing)}"
        )

    valid_rows: list[dict[str, object]] = []
    invalid_rows: list[dict[str, object]] = []
    for row_number, (_, row) in enumerate(catalog.iterrows(), start=1):
        record = row.to_dict()
        try:
            ProductoMercadona.model_validate(record)
        except PydanticValidationError as exc:
            details = "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors()
            )
            invalid_rows.append(
                {
                    **record,
                    "row_number": row_number,
                    "validation_error": details,
                }
            )
        else:
            valid_rows.append(record)

    return (
        pd.DataFrame(valid_rows, columns=catalog.columns),
        pd.DataFrame(
            invalid_rows,
            columns=[*catalog.columns, "row_number", "validation_error"],
        ),
    )