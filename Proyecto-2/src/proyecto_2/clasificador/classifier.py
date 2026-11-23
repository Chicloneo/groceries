"""Carga y aplicación del clasificador guardado de categorías y subcategorías."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import joblib
import pandas as pd
from sklearn.pipeline import Pipeline

PROJECT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_MODEL_PATH = PROJECT_DIR / "models" / "clasificador_productos.joblib"


def _top_predictions(
    model: Pipeline,
    texts: list[str],
    top_k: int,
) -> list[list[tuple[str, float]]]:
    probabilities = model.predict_proba(texts)
    classes = model.classes_
    top_k = max(1, min(top_k, len(classes)))
    order = probabilities.argsort(axis=1)[:, ::-1][:, :top_k]
    return [
        [(str(classes[index]), float(row[index])) for index in indices]
        for row, indices in zip(probabilities, order)
    ]


@dataclass
class ProductClassifier:
    """Modelos guardados para categoría y subcategoría."""

    category_model: Pipeline
    subcategory_model: Pipeline
    metrics: dict[str, float | int] = field(default_factory=dict)
    trained_at: str = ""
    C: float = 10.0

    def predict(
        self,
        names: str | Iterable[str],
        top_k: int = 3,
    ) -> pd.DataFrame:
        if isinstance(names, str):
            texts = [names]
        else:
            texts = [str(name) for name in names]
        texts = [text.strip() for text in texts if text and text.strip()]
        if not texts:
            raise ValueError("Hay que proporcionar al menos un nombre de producto.")

        categories = _top_predictions(self.category_model, texts, top_k)
        subcategories = _top_predictions(self.subcategory_model, texts, top_k)

        return pd.DataFrame(
            {
                "nombre": texts,
                "categoria": [options[0][0] for options in categories],
                "confianza_categoria": [
                    round(options[0][1], 3) for options in categories
                ],
                "subcategoria": [options[0][0] for options in subcategories],
                "confianza_subcategoria": [
                    round(options[0][1], 3) for options in subcategories
                ],
                "alternativas_subcategoria": [
                    "; ".join(
                        f"{label} ({score:.2f})"
                        for label, score in options[1:]
                    )
                    for options in subcategories
                ],
            }
        )

    @classmethod
    def load(cls, path: str | Path = DEFAULT_MODEL_PATH) -> "ProductClassifier":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"No existe el modelo: {path}")

        payload = joblib.load(path)
        required = {"category_model", "subcategory_model"}
        if not required.issubset(payload):
            raise ValueError("El archivo no es un modelo compatible.")

        return cls(
            category_model=payload["category_model"],
            subcategory_model=payload["subcategory_model"],
            metrics=payload.get("metrics", {}),
            trained_at=payload.get("trained_at", ""),
            C=payload.get("C", 10.0),
        )
