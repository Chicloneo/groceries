"""CLI para entrenar el clasificador y clasificar productos nuevos."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from time import perf_counter

import pandas as pd

from proyecto_2.classifier import (
    DEFAULT_DATA_PATH,
    DEFAULT_MODEL_PATH,
    ProductClassifier,
    train_classifier,
)
from proyecto_2.mock_products import MOCK_PRODUCTS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Entrena un clasificador de categorías y subcategorías y lo aplica "
            "a productos nuevos."
        )
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA_PATH,
        help=(
            "CSV de entrenamiento "
            "(por defecto, Proyecto-1/Data/productos_madrid_centro.csv)."
        ),
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help="Ruta del modelo joblib que se carga o se guarda.",
    )
    parser.add_argument(
        "--retrain",
        action="store_true",
        help="Reentrena aunque ya exista un modelo guardado.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Proporción del catálogo reservada para evaluar (0-1).",
    )
    parser.add_argument(
        "--C",
        type=float,
        default=10.0,
        help="Inverso de la regularización de la regresión logística.",
    )
    parser.add_argument(
        "--name",
        action="append",
        metavar="NOMBRE",
        help="Nombre de un producto nuevo. Se puede repetir varias veces.",
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        help="CSV con productos nuevos que se quieren clasificar.",
    )
    parser.add_argument(
        "--name-column",
        default="nombre",
        help="Columna del CSV de entrada con el nombre del producto.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        help="Guarda las predicciones en este CSV.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Número de alternativas de subcategoría que se calculan.",
    )
    return parser


def _load_or_train(args: argparse.Namespace) -> ProductClassifier:
    # Reutilizar el modelo evita volver a entrenarlo en cada consulta.
    if args.model.exists() and not args.retrain:
        try:
            classifier = ProductClassifier.load(args.model)
            print(f"Modelo cargado desde {args.model}", file=sys.stderr)
            return classifier
        except Exception as exc:  # modelo antiguo o archivo corrupto
            # Avisamos antes de reconstruirlo para que el reentrenamiento no pase inadvertido.
            print(
                f"No se pudo cargar {args.model} ({exc}); se reentrena.",
                file=sys.stderr,
            )

    print(
        f"Entrenando con {args.data} (esto puede tardar unos segundos)...",
        file=sys.stderr,
    )
    started = perf_counter()
    classifier = train_classifier(
        data_path=args.data,
        test_size=args.test_size,
        C=args.C,
    )
    elapsed = perf_counter() - started
    classifier.save(args.model)
    print(
        f"Modelo entrenado en {elapsed:.1f} s y guardado en {args.model}",
        file=sys.stderr,
    )
    return classifier


def _collect_names(args: argparse.Namespace) -> list[str]:
    # Se da prioridad al CSV y luego a los --name; la lista de ejemplo solo se
    # usa cuando el usuario no indicó una entrada.
    if args.input_csv is not None:
        frame = pd.read_csv(args.input_csv, encoding="utf-8-sig", dtype=str)
        if args.name_column not in frame.columns:
            raise ValueError(
                f"El CSV no contiene la columna '{args.name_column}'. "
                f"Columnas disponibles: {list(frame.columns)}"
            )
        names = frame[args.name_column].dropna().astype(str).tolist()
        if not names:
            raise ValueError("El CSV de entrada no contiene nombres de producto.")
        return names

    if args.name:
        return list(args.name)

    print(
        "No se indicaron productos: se usa la lista de ejemplo "
        "(--name o --input-csv para clasificar los tuyos).",
        file=sys.stderr,
    )
    return list(MOCK_PRODUCTS)


def _format_metrics(metrics: dict[str, float | int]) -> str:
    lines = [
        f"Productos de entrenamiento: {metrics.get('productos', 0)} "
        f"({metrics.get('num_categorias', 0)} categorías, "
        f"{metrics.get('num_subcategorias', 0)} subcategorías)"
    ]
    if "accuracy_categoria_test" in metrics:
        # Las métricas de prueba no existen si el clasificador se cargó sin
        # haber guardado resultados de evaluación.
        lines.append(
            "Categoría    — exactitud test: "
            f"{metrics['accuracy_categoria_test']:.1%} | "
            f"F1 macro: {metrics['macro_f1_categoria_test']:.1%}"
        )
        lines.append(
            "Subcategoría — exactitud test: "
            f"{metrics['accuracy_subcategoria_test']:.1%} | "
            f"F1 macro: {metrics['macro_f1_subcategoria_test']:.1%}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        classifier = _load_or_train(args)
        names = _collect_names(args)
        predictions = classifier.predict(names, top_k=args.top_k)
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print()
    print(_format_metrics(classifier.metrics))
    print()
    columns = [
        "nombre",
        "categoria",
        "confianza_categoria",
        "subcategoria",
        "confianza_subcategoria",
    ]
    with pd.option_context("display.max_colwidth", 70, "display.width", 220):
        print(predictions[columns].to_string(index=False))

    if args.output_csv is not None:
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        predictions.to_csv(args.output_csv, index=False, encoding="utf-8-sig")
        print(f"\nPredicciones guardadas en {args.output_csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
