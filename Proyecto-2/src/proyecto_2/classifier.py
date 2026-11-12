"""Clasificador de categorías y subcategorías para productos del catálogo.

El modelo aprende a partir del nombre del producto. Se entrenan dos
clasificadores independientes con la misma representación de texto:

* ``categoria``: 24 clases (p. ej. "Bodega", "Limpieza y hogar").
* ``subcategoria``: ~134 clases (p. ej. "Cerveza", "Leche y bebidas vegetales").

Antes de entrenar se eliminan los duplicados por nombre: el catálogo repite los
mismos productos en cada código postal. Cuando un nombre aparece con etiquetas
distintas se conserva la combinación (categoría, subcategoría) más frecuente.

Uso rápido::

    from proyecto_2.classifier import train_classifier

    modelo = train_classifier()
    print(modelo.predict(["Leche de avena sin azúcar 1 L"]))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

RANDOM_STATE = 42
NAME_COLUMN = "nombre"
CATEGORY_COLUMN = "categoria"
SUBCATEGORY_COLUMN = "subcategoria"

PROJECT_DIR = Path(__file__).resolve().parents[2]
# Proyecto 2 lee el CSV creado por la extracción de Proyecto 1; no mantiene
# una segunda copia del catálogo.
DEFAULT_DATA_PATH = (
    PROJECT_DIR.parent / "Proyecto-1" / "Data" / "productos_madrid_centro.csv"
)
DEFAULT_MODEL_PATH = PROJECT_DIR / "models" / "clasificador_productos.joblib"


def load_products(path: str | Path = DEFAULT_DATA_PATH) -> pd.DataFrame:
    """Carga el catálogo y devuelve solo las columnas necesarias.

    El CSV original incluye una fila por producto y código postal, además de
    columnas de formato y precio que el clasificador no utiliza.
    """

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No existe el catálogo de productos: {path}")

    # El CSV puede llevar BOM y estos campos se usan como texto, no como números.
    frame = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    missing = {
        NAME_COLUMN,
        CATEGORY_COLUMN,
        SUBCATEGORY_COLUMN,
    } - set(frame.columns)
    if missing:
        raise ValueError(
            f"El CSV no contiene las columnas obligatorias: {sorted(missing)}"
        )

    return frame[[NAME_COLUMN, CATEGORY_COLUMN, SUBCATEGORY_COLUMN]].copy()


def prepare_dataset(frame: pd.DataFrame) -> pd.DataFrame:
    """Limpia y deduplica el catálogo dejando un producto por nombre.

    - Elimina filas con nombre o etiquetas vacías.
    - Normaliza espacios en el nombre.
    - Si un nombre tiene varias etiquetas, se queda con la más frecuente
      (desempate alfabético para que el resultado sea reproducible).
    """

    missing = {
        NAME_COLUMN,
        CATEGORY_COLUMN,
        SUBCATEGORY_COLUMN,
    } - set(frame.columns)
    if missing:
        raise ValueError(
            f"Faltan columnas obligatorias: {sorted(missing)}"
        )

    data = frame[[NAME_COLUMN, CATEGORY_COLUMN, SUBCATEGORY_COLUMN]].copy()
    data = data.dropna(subset=[NAME_COLUMN, CATEGORY_COLUMN, SUBCATEGORY_COLUMN])
    data[NAME_COLUMN] = data[NAME_COLUMN].str.strip()
    data[CATEGORY_COLUMN] = data[CATEGORY_COLUMN].str.strip()
    data[SUBCATEGORY_COLUMN] = data[SUBCATEGORY_COLUMN].str.strip()
    data = data[
        data[NAME_COLUMN].ne("")
        & data[CATEGORY_COLUMN].ne("")
        & data[SUBCATEGORY_COLUMN].ne("")
    ]

    # Hay una fila por CP en el catálogo, así que votamos una sola etiqueta por
    # nombre. El orden alfabético resuelve los empates de forma repetible.
    counts = (
        data.groupby(
            [NAME_COLUMN, CATEGORY_COLUMN, SUBCATEGORY_COLUMN],
            as_index=False,
        )
        .size()
        .sort_values(
            [NAME_COLUMN, "size", CATEGORY_COLUMN, SUBCATEGORY_COLUMN],
            ascending=[True, False, True, True],
        )
    )
    return (
        counts.drop_duplicates(subset=NAME_COLUMN)
        .drop(columns="size")
        .reset_index(drop=True)
    )


def build_pipeline(C: float = 10.0) -> Pipeline:
    """Crea el pipeline TF-IDF + regresión logística.

    Se combinan n-gramas de palabras (1-2) y de caracteres (3-5). Los segundos
    ayudan con marcas, errores ortográficos y palabras compuestas del catálogo.
    """

    # Las palabras capturan términos completos; los caracteres ayudan con
    # marcas y pequeñas diferencias de escritura.
    features = FeatureUnion(
        [
            (
                "palabras",
                TfidfVectorizer(
                    analyzer="word",
                    ngram_range=(1, 2),
                    min_df=1,
                    sublinear_tf=True,
                    strip_accents="unicode",
                ),
            ),
            (
                "caracteres",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=2,
                    sublinear_tf=True,
                    strip_accents="unicode",
                ),
            ),
        ]
    )
    model = LogisticRegression(
        C=C,
        class_weight="balanced",
        max_iter=1000,
        solver="lbfgs",
        random_state=RANDOM_STATE,
    )
    return Pipeline([("features", features), ("modelo", model)])


def split_dataset(
    frame: pd.DataFrame,
    test_size: float = 0.2,
    random_state: int = RANDOM_STATE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa los datos y garantiza que cada subcategoría aparezca en ambos."""

    data = prepare_dataset(frame)
    class_counts = data[SUBCATEGORY_COLUMN].value_counts()
    if class_counts.min() < 2:
        raise ValueError(
            "Cada subcategoría necesita al menos 2 productos para usar "
            "un split estratificado."
        )

    train, test = train_test_split(
        data,
        test_size=test_size,
        random_state=random_state,
        stratify=data[SUBCATEGORY_COLUMN],
    )

    # Con clases muy pequeñas, la estratificación puede dejar una subcategoría
    # solo en un conjunto. Movemos un producto real al otro lado; no lo copiamos.
    for subcategory in class_counts.index:
        train_rows = train.loc[train[SUBCATEGORY_COLUMN].eq(subcategory)]
        test_rows = test.loc[test[SUBCATEGORY_COLUMN].eq(subcategory)]
        if train_rows.empty:
            index = test_rows.index[0]
            train = pd.concat([train, test.loc[[index]]])
            test = test.drop(index=index)
        elif test_rows.empty:
            index = train_rows.index[0]
            test = pd.concat([test, train.loc[[index]]])
            train = train.drop(index=index)

    return train.reset_index(drop=True), test.reset_index(drop=True)


def _top_predictions(
    model: Pipeline, texts: list[str], top_k: int
) -> list[list[tuple[str, float]]]:
    """Devuelve las ``top_k`` clases más probables para cada texto."""

    probabilities = model.predict_proba(texts)
    classes = model.classes_
    # Evita devolver cero alternativas si se pide top_k <= 0, o más clases de
    # las que aprendió el modelo.
    top_k = max(1, min(top_k, len(classes)))
    order = probabilities.argsort(axis=1)[:, ::-1][:, :top_k]
    return [
        [(str(classes[index]), float(row[index])) for index in indices]
        for row, indices in zip(probabilities, order)
    ]


@dataclass
class ProductClassifier:
    """Par de modelos entrenados (categoría y subcategoría)."""

    category_model: Pipeline
    subcategory_model: Pipeline
    metrics: dict[str, float | int] = field(default_factory=dict)
    trained_at: str = ""
    C: float = 10.0
    test_predictions: pd.DataFrame = field(
        default_factory=pd.DataFrame, repr=False
    )

    def predict(
        self, names: str | Iterable[str], top_k: int = 3
    ) -> pd.DataFrame:
        """Clasifica uno o varios nombres de producto.

        Devuelve un DataFrame con la categoría, la subcategoría y sus
        probabilidades. ``alternativas_subcategoria`` contiene las siguientes
        opciones del top-k, útil para revisar casos dudosos.
        """

        if isinstance(names, str):
            texts = [names]
        else:
            texts = [str(name) for name in names]
        # Los nombres vacíos no aportan nada al modelo y pueden dar resultados
        # engañosos, así que se descartan antes de predecir.
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

    def save(self, path: str | Path = DEFAULT_MODEL_PATH) -> Path:
        """Guarda los modelos y sus métricas en un único archivo joblib."""

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Ambos modelos y sus métricas se guardan juntos para mantenerlos ligados.
        joblib.dump(
            {
                "format_version": 1,
                "trained_at": self.trained_at,
                "metrics": self.metrics,
                "C": self.C,
                "category_model": self.category_model,
                "subcategory_model": self.subcategory_model,
            },
            path,
        )
        return path

    @classmethod
    def load(cls, path: str | Path = DEFAULT_MODEL_PATH) -> "ProductClassifier":
        """Carga un modelo guardado con :meth:`save`."""

        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"No existe el modelo: {path}")

        payload = joblib.load(path)
        required = {"category_model", "subcategory_model"}
        if not required.issubset(payload):
            raise ValueError(f"El archivo {path} no es un modelo compatible.")

        return cls(
            category_model=payload["category_model"],
            subcategory_model=payload["subcategory_model"],
            metrics=payload.get("metrics", {}),
            trained_at=payload.get("trained_at", ""),
            C=payload.get("C", 10.0),
        )


def fit_classifier(
    train_frame: pd.DataFrame,
    test_frame: pd.DataFrame | None = None,
    C: float = 10.0,
) -> ProductClassifier:
    """Entrena ambos clasificadores con un conjunto de entrenamiento.

    Si se proporciona ``test_frame`` se calculan las métricas de evaluación y
    se guardan las predicciones en ``test_predictions``.
    """

    train = prepare_dataset(train_frame)
    if train.empty:
        raise ValueError("El conjunto de entrenamiento está vacío.")

    # Categoría y subcategoría son dos objetivos distintos, aunque comparten el
    # mismo texto de entrada.
    category_model = build_pipeline(C).fit(train[NAME_COLUMN], train[CATEGORY_COLUMN])
    subcategory_model = build_pipeline(C).fit(
        train[NAME_COLUMN], train[SUBCATEGORY_COLUMN]
    )

    train_category_pred = category_model.predict(train[NAME_COLUMN])
    train_subcategory_pred = subcategory_model.predict(train[NAME_COLUMN])

    metrics: dict[str, float | int] = {
        "productos": len(train),
        "num_categorias": int(train[CATEGORY_COLUMN].nunique()),
        "num_subcategorias": int(train[SUBCATEGORY_COLUMN].nunique()),
        "accuracy_categoria_train": round(
            accuracy_score(train[CATEGORY_COLUMN], train_category_pred), 4
        ),
        "accuracy_subcategoria_train": round(
            accuracy_score(train[SUBCATEGORY_COLUMN], train_subcategory_pred), 4
        ),
        "prueba": 0,
    }

    classifier = ProductClassifier(
        category_model=category_model,
        subcategory_model=subcategory_model,
        metrics=metrics,
        trained_at=datetime.now().isoformat(timespec="seconds"),
        C=C,
    )

    if test_frame is not None and not test_frame.empty:
        test = prepare_dataset(test_frame)
        category_pred = category_model.predict(test[NAME_COLUMN])
        subcategory_pred = subcategory_model.predict(test[NAME_COLUMN])

        classifier.metrics.update(
            {
                "prueba": len(test),
                "accuracy_categoria_test": round(
                    accuracy_score(test[CATEGORY_COLUMN], category_pred), 4
                ),
                "macro_f1_categoria_test": round(
                    f1_score(
                        test[CATEGORY_COLUMN], category_pred, average="macro"
                    ),
                    4,
                ),
                "accuracy_subcategoria_test": round(
                    accuracy_score(test[SUBCATEGORY_COLUMN], subcategory_pred),
                    4,
                ),
                "macro_f1_subcategoria_test": round(
                    f1_score(
                        test[SUBCATEGORY_COLUMN],
                        subcategory_pred,
                        average="macro",
                    ),
                    4,
                ),
            }
        )

        classifier.test_predictions = test.rename(
            columns={
                CATEGORY_COLUMN: "categoria_real",
                SUBCATEGORY_COLUMN: "subcategoria_real",
            }
        ).assign(
            categoria_predicha=category_pred,
            subcategoria_predicha=subcategory_pred,
        )

    return classifier


def train_classifier(
    frame: pd.DataFrame | None = None,
    data_path: str | Path | None = None,
    test_size: float = 0.2,
    random_state: int = RANDOM_STATE,
    C: float = 10.0,
) -> ProductClassifier:
    """Carga los datos, separa train/test y entrena el clasificador."""

    # Aceptar un DataFrame permite entrenar con fixtures sin leer el CSV real.
    path = Path(data_path) if data_path is not None else DEFAULT_DATA_PATH
    dataset = prepare_dataset(frame) if frame is not None else load_products(path)
    train, test = split_dataset(dataset, test_size=test_size, random_state=random_state)
    return fit_classifier(train, test, C=C)
