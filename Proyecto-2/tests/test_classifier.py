"""Pruebas del clasificador cargado."""

import pytest

from proyecto_2.clasificador.classifier import ProductClassifier


def test_predict_rejects_empty_input():
    classifier = ProductClassifier.load()

    with pytest.raises(ValueError, match="al menos un nombre"):
        classifier.predict([])


def test_saved_classifier_predicts_category_and_subcategory():
    classifier = ProductClassifier.load()

    predictions = classifier.predict(["Leche entera 2 L"])

    assert predictions.loc[0, "categoria"] == "Huevos, leche y mantequilla"
    assert predictions.loc[0, "subcategoria"] == "Leche y bebidas vegetales"
