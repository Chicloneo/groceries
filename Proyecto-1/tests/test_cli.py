import json

from proyecto_1.cli import main


def test_cli_prints_a_report_for_the_input_csv(tmp_path, products, capsys):
    path = tmp_path / "products.csv"
    products.to_csv(path, index=False)

    exit_code = main(["--input", str(path)])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["filas_totales"] == len(products)
    assert output["filas_validas"] == len(products)
    assert output["metricas"]["envases_mas_frecuentes"] == [
        {"envase": "Botella", "apariciones": 2}
    ]
