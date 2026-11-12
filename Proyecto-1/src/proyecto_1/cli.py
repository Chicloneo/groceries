"""Punto de entrada para analizar un CSV de productos."""

import argparse
import json
import sys
from pathlib import Path

from proyecto_1.loader import DataLoadError, load_catalog
from proyecto_1.metrics import calculate_metrics
from proyecto_1.validator import CatalogValidationError, validate_catalog


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Valida y resume un catálogo de productos de Mercadona."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Ruta al CSV del catálogo.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        catalog = load_catalog(args.input)
        valid, invalid = validate_catalog(catalog)
        metrics = calculate_metrics(valid)
    except (DataLoadError, CatalogValidationError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    report = {
        "filas_totales": len(catalog),
        "filas_validas": len(valid),
        "filas_invalidas": len(invalid),
        "errores_validacion": invalid[
            ["row_number", "validation_error"]
        ].to_dict(orient="records"),
        "metricas": metrics,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if not invalid.empty else 0


if __name__ == "__main__":
    raise SystemExit(main())
