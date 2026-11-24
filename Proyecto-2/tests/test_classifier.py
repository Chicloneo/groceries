"""Pruebas del clasificador cargado."""

import hashlib
import json
from pathlib import Path

import pytest

from proyecto_2.clasificador.classifier import ProductClassifier


def test_predict_rejects_empty_input():
    classifier = ProductClassifier.load()

    with pytest.raises(ValueError, match="al menos un nombre"):
        classifier.predict([])


@pytest.mark.integration
def test_saved_classifier_predicts_category_and_subcategory():
    project_dir = Path(__file__).resolve().parents[1]
    model_path = project_dir / "models" / "clasificador_productos.joblib"
    manifest_path = project_dir / "models" / "clasificador_productos.manifest.json"

    assert model_path.is_file()
    assert manifest_path.is_file()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    assert actual_hash == manifest["sha256"]

    classifier = ProductClassifier.load()

    predictions = classifier.predict(["Leche entera 2 L"])

    assert predictions.loc[0, "categoria"] == "Huevos, leche y mantequilla"
    assert predictions.loc[0, "subcategoria"] == "Leche y bebidas vegetales"
