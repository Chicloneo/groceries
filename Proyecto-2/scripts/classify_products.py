#!/usr/bin/env python
"""Script de ejemplo para clasificar productos nuevos.

Desde ``Proyecto-2/``::

    uv run python scripts/classify_products.py --name "Leche de avena 1 L"
    uv run python scripts/classify_products.py --input-csv productos.csv \
        --output-csv predicciones.csv

El script delega en ``proyecto_2.cli``; toda la lógica reutilizable está en
``proyecto_2.classifier`` y puede importarse desde un notebook o desde otro
programa.
"""

from proyecto_2.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
