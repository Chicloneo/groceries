import json
from pathlib import Path

import pytest

from proyecto_1.cli import main


@pytest.mark.integration
def test_cli_processes_checked_in_catalog_sample(capsys):
    sample_path = Path(__file__).resolve().parents[1] / "Data" / "aux.csv"

    exit_code = main(["--input", str(sample_path)])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["filas_totales"] == 4275
    assert output["filas_validas"] == 4275
    assert output["filas_invalidas"] == 0
